#!/usr/bin/env bash
# AI 热点短视频选题流水线入口（可 cron / launchd / 手动）
# 固定顺序：TrendRadar → (Grok X 补充) → cheat 筛选 → 标准化脚本 → 留存
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/miniconda3/bin:$PATH"
export TZ=Asia/Shanghai

DATE="$(date +%Y-%m-%d)"
TIME="$(date +%H%M%S)"
ARCH="$ROOT/data/archive/$DATE"
LOG="$ROOT/logs/${DATE}.log"
mkdir -p "$ARCH" "$ROOT/logs" "$ROOT/output/latest" "$ROOT/data/history"

exec >>"$LOG" 2>&1
echo "======== RUN $DATE $TIME ========"
cd "$ROOT"

# 依赖：尽量用系统/conda python3；缺 yaml 时降级跳过或装到 user
PY="${PYTHON:-python3}"
if ! "$PY" -c "import yaml" 2>/dev/null; then
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$PY" pyyaml -q 2>/dev/null || "$PY" -m pip install --user pyyaml -q || true
  else
    "$PY" -m pip install --user pyyaml -q || true
  fi
fi

echo "[1/5] TrendRadar crawl + AI export"
"$PY" "$ROOT/scripts/fetch_trendradar_ai.py" \
  --config "$ROOT/config/pipeline.yaml" \
  --out "$ARCH/01_trendradar.json"

# Phase 2: 若已有 X 补充文件则合并；否则先用 TrendRadar 单源，后续 Grok Skill 会补 X
X_FILE="$ARCH/02_x_raw.json"
WEB_FILE="$ARCH/02_web_raw.json"
if [[ ! -f "$X_FILE" ]]; then
  echo '{"items":[],"note":"X 数据由 Skill/Grok 头less 补写此文件"}' >"$X_FILE"
fi
if [[ ! -f "$WEB_FILE" ]]; then
  echo '{"items":[],"note":"小红书/科技站 web 补充由 Skill 补写"}' >"$WEB_FILE"
fi

echo "[2/5] Merge + dedupe"
"$PY" "$ROOT/scripts/merge_dedupe.py" \
  --trendradar "$ARCH/01_trendradar.json" \
  --x "$X_FILE" \
  --web "$WEB_FILE" \
  --out "$ARCH/02_merged.json"

echo "[3/5] Score + filter (cheat-on-content style)"
"$PY" "$ROOT/scripts/score_filter.py" \
  --merged "$ARCH/02_merged.json" \
  --out "$ARCH/03_scored.json" \
  --top-n 8 \
  --master-index "$ROOT/data/history/master_index.jsonl"

echo "[4/5] Build content packages + delivery tables"
"$PY" "$ROOT/scripts/build_packages.py" \
  --scored "$ARCH/03_scored.json" \
  --out-json "$ARCH/04_packages.json" \
  --out-md "$ROOT/output/latest/delivery.md" \
  --out-csv "$ROOT/output/latest/delivery.csv" \
  --master-index "$ROOT/data/history/master_index.jsonl"

# 同步一份带时间戳的 latest
cp -f "$ROOT/output/latest/delivery.md" "$ARCH/04_delivery.md"
cp -f "$ROOT/output/latest/delivery.csv" "$ARCH/04_delivery.csv"

echo "[5/5] Optional: Grok headless enrich (X + 精修文案)"
GROK_BIN="${GROK_BIN:-$HOME/.grok/bin/grok}"
if [[ "${SKIP_GROK:-0}" != "1" && -x "$GROK_BIN" ]]; then
  PROMPT_FILE="$ARCH/05_grok_prompt.txt"
  cat >"$PROMPT_FILE" <<EOF
严格执行项目 Skill /ai-hotspot-pipeline 的「补全模式」：

工作目录: $ROOT
今日归档: $ARCH

已完成 Phase1-4 脚本产物。你必须：
1) 用 X 搜索工具按 config/pipeline.yaml 的 x_sources.queries 抓近 12h AI 相关推文/博主动态/新工具，写入 $ARCH/02_x_raw.json（items 数组，字段 title/url/source/snapshot_text/published_at/interaction）
2) 用 web_search 补充小红书 AI 热点与科技站遗漏，写入 $ARCH/02_web_raw.json
3) 重新运行: bash scripts/run_pipeline.sh 时设置 SKIP_GROK=1 避免递归；或直接重跑 merge→score→package 三步 python 脚本
4) 读取 data/history/patterns.md 与 master_index.jsonl，优化评分判断说明，追加今日规律到 patterns.md（只追加，不删历史）
5) 对 output/latest/delivery.md 中保留选题的「封面标题/钩子/拍摄流程」做质量精修（保持表格结构）
6) 最终只输出交付表路径与 kept 数量，不要废话

禁止删除 data/archive 与 data/history 下任何历史文件。
EOF
  # 避免无限递归
  if [[ "${GROK_ENRICH_DONE:-0}" != "1" ]]; then
    export GROK_ENRICH_DONE=1
    "$GROK_BIN" -p "$(cat "$PROMPT_FILE")" \
      --cwd "$ROOT" \
      --yolo \
      --permission-mode bypassPermissions \
      --max-turns 40 \
      --output-format plain \
      || echo "[warn] grok enrich failed (base tables still available)"
  fi
else
  echo "[info] skip grok enrich (SKIP_GROK=$SKIP_GROK or grok missing)"
fi

echo "DONE → $ROOT/output/latest/delivery.md"
echo "ARCHIVE → $ARCH"
