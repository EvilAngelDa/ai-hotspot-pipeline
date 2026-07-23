# ai-hotspot-pipeline

**AI 热点短视频选题流水线 Skill**

固定顺序串起三件工具，每日产出可拍摄选题表：

```text
TrendRadar 热榜爬取
    → Grok X / Web 补漏合并去重
    → cheat-on-content 风格筛选（爆火概率 / 红利 / 内卷）
    → 标准化短视频方案（封面 / 钩子 / 分镜 / 时长 / 画面）
```

跨 Agent 通用（Agent Skills 标准：`SKILL.md`）。  
适用于 **Grok Build / Codex / Claude Code / Cursor** 等会加载 skill 的工具。

| 字段 | 值 |
|------|-----|
| **Skill 名** | `ai-hotspot-pipeline` |
| **Slash** | `/ai-hotspot-pipeline` |
| **触发词** | 跑热点流水线 / 每日选题 / AI热点选题 / 补全模式 |

---

## 安装

```bash
git clone https://github.com/EvilAngelDa/ai-hotspot-pipeline.git
cd ai-hotspot-pipeline
bash install.sh          # 复制到 ~/.grok|claude|codex/skills/
# 或
bash install.sh --symlink --grok
```

| 工具 | 用户级目录 |
|------|------------|
| Grok | `~/.grok/skills/ai-hotspot-pipeline/` |
| Claude Code | `~/.claude/skills/ai-hotspot-pipeline/` |
| Codex | `~/.codex/skills/ai-hotspot-pipeline/` |

依赖：

1. [TrendRadar](https://github.com/sansan0/TrendRadar) 已安装并可 `uv run python -m trendradar`
2. `export TRENDRADAR_ROOT=~/tools/TrendRadar`（按本机路径改）
3. Python 3.10+（脚本层）；Grok 会话用于 X 补漏与文案精修

---

## 使用

### Agent 对话

```text
/ai-hotspot-pipeline
# 或
跑热点流水线
```

### 命令行

```bash
# 在本仓库或已初始化的内容工作区
bash scripts/run_pipeline.sh

# 仅脚本层（跳过 Grok 二次精修）
SKIP_GROK=1 bash scripts/run_pipeline.sh
```

### 每日 09:00（macOS）

```bash
# 把 example 里的 __INSTALL_DIR__ / __HOME__ 替换后 load
cp launchd/com.ai-hotspot-pipeline.plist.example ~/Library/LaunchAgents/com.ai-hotspot-pipeline.plist
# 编辑路径后：
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ai-hotspot-pipeline.plist
```

---

## 交付物

| 路径 | 说明 |
|------|------|
| `output/latest/delivery.md` | 总表 + 逐条拍摄方案 |
| `output/latest/delivery.csv` | 表格导入 |
| `data/archive/YYYY-MM-DD/` | 当日全阶段 JSON（永不清空） |
| `data/history/master_index.jsonl` | 历史 kept 索引（只追加） |
| `data/history/patterns.md` | 往期规律（只追加） |

---

## 仓库结构

```text
ai-hotspot-pipeline/
  SKILL.md                 # Agent 总协议（必须）
  README.md
  install.sh
  config/
    pipeline.yaml
    ai_keywords.txt
  scripts/
    run_pipeline.sh
    fetch_trendradar_ai.py
    merge_dedupe.py
    score_filter.py
    build_packages.py
  launchd/
    com.ai-hotspot-pipeline.plist.example
  references/
    tool-chain.md
  examples/
    delivery-sample.md
```

---

## 更新

```bash
cd /path/to/ai-hotspot-pipeline
git pull
bash install.sh --copy --all   # 或 --symlink 则 pull 即生效
```

维护者（EvilAngelDa）会在 skill 有改动时继续 push 到本仓库。

---

## License

MIT
