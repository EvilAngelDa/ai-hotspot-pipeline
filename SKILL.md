---
name: ai-hotspot-pipeline
description: >
  AI 热点短视频选题流水线。严格按固定顺序执行：① TrendRadar 爬取抖音/B站/科技源近 12h AI 热点
  → ② Grok X 实时补推特新兴 AI 话题并与热榜合并去重 → ③ 按 cheat-on-content 7 维 rubric 估
  6~24h 爆火概率/红利剩余/内卷度并硬剔除下行/同质化/无实操资讯 → ④ 对保留选题产出封面标题、
  口播钩子、分镜拍摄流程、时长、画面参考。每日 09:00 自动跑；全部选题/打分/方案写入
  data/archive 与 master_index 永不清空。触发词："跑热点流水线"/"每日选题"/"AI热点选题"/
  "/ai-hotspot-pipeline"/"早上选题"/"补全模式"。
argument-hint: "[full|enrich|status]"
compatibility: Requires TrendRadar at ~/tools/TrendRadar, uv, Python3; Grok X tools; project scripts under scripts/
---

# /ai-hotspot-pipeline — AI 热点短视频选题流水线

## 不可妥协的执行顺序

**必须按 1→2→3→4 顺序，禁止跳步、禁止颠倒。**

```
① TrendRadar 批量爬取 + AI 过滤导出
        ↓
② Grok X 实时补漏 + 小红书/科技 web 补漏 → 合并去重素材表
        ↓
③ cheat-on-content 风格热度预测与硬剔除
        ↓
④ 标准化短视频内容包 + 表格交付
        ↓
⑤ 留存归档（只追加，永不删历史）
```

配置单一来源：`config/pipeline.yaml`  
关键词：`config/ai_keywords.txt`  
一键脚本：`bash scripts/run_pipeline.sh`

---

## 模式

| 用户说 | 模式 | 行为 |
|---|---|---|
| `/ai-hotspot-pipeline` / `跑热点流水线` / `每日选题` | **full** | 完整 ①–⑤ |
| `补全模式` / enrich | **enrich** | 假定 ① 已有，只做 ②–⑤ 精修 |
| `流水线状态` / status | **status** | 只读最新交付与历史条数 |

默认 **full**。

---

## Phase ① — TrendRadar（固定）

### 目标源

| 目标 | 实现 | 备注 |
|---|---|---|
| 抖音 | platform `douyin` | 热榜 rank + rank_history |
| B 站 | platform `bilibili-hot-search` | 同上 |
| 科技资讯 | RSS（HN 等）+ 综合热榜 | 标题 AI 关键词过滤 |
| 小红书 | **无原生源** | Phase ② `web_search` 补 |
| 近 12 小时 | `lookback_hours: 12` | 脚本过滤 |

### 动作（按序）

1. 运行：
   ```bash
   python3 scripts/fetch_trendradar_ai.py --config config/pipeline.yaml
   ```
   （脚本内会 `uv run python -m trendradar` 触发爬取，再读 SQLite 导出）
2. 读取产物：`data/archive/YYYY-MM-DD/01_trendradar.json`
3. 校验 `count >= 0`；若 crawl 失败，记录 `notes` 并继续（用已有 DB），不得中止整链除非 DB 全空且爬取失败

### 导出字段（每条）

`id, title, source, platform_id, url, published_at, keywords, heat_rank, heat_velocity, interaction, snapshot_text`

> 公开热榜通常无完整点赞/评论原始数；`interaction` 用 rank + crawl_count + rank_history 作代理。诚实写入，禁止编造精确互动数。

---

## Phase ② — Grok X + Web 补漏 → 统一素材表

### 2.1 X（推特）— 必须使用原生 X 工具

按 `config/pipeline.yaml` → `x_sources.queries` **逐条**调用：

- `x_keyword_search`（`mode: Latest`，可加 `min_faves`）
- 必要时 `x_semantic_search` 补「新兴 AI 工具 / 博主动态」

提取为 items：

```json
{
  "title": "推文核心议题一句话",
  "source": "x:twitter",
  "url": "https://x.com/...",
  "snapshot_text": "原文摘要",
  "published_at": "ISO",
  "interaction": {"likes": 0, "reposts": 0, "replies": 0},
  "keywords": ["AI", "..."]
}
```

写入：`data/archive/YYYY-MM-DD/02_x_raw.json`（`{"items":[...]}`）

### 2.2 小红书 + 科技站补漏

- `web_search`：`小红书 AI 热门` / `小红书 AIGC 教程 热点` / 当日 AI 产品名
- 可选 `web_fetch` 打开结果页提炼标题
- 写入：`data/archive/YYYY-MM-DD/02_web_raw.json`

### 2.3 合并去重

```bash
python3 scripts/merge_dedupe.py \
  --trendradar data/archive/YYYY-MM-DD/01_trendradar.json \
  --x data/archive/YYYY-MM-DD/02_x_raw.json \
  --web data/archive/YYYY-MM-DD/02_web_raw.json \
  --out data/archive/YYYY-MM-DD/02_merged.json
```

规则：同 id 去重 + 标题近重复（bigram Jaccard≥0.72）保留一条。  
输出 = **统一素材表**。

---

## Phase ③ — cheat-on-content 热度预测与剔除

### 对齐 cheat-on-content

- 维度名与 starter rubric **opinion-video-zero** 一致：`ER HP QL NA AB SR SAT`
- 综合分：`(sum dims / 7) * 2` → 0–10
- **额外**输出（用户要求）：
  - `viral_prob_6h` / `viral_prob_24h`（未来 6~24h 爆火概率）
  - `traffic_window_hours`（流量红利剩余时长）
  - `competition_score`（同行内卷 0–10）
- 读 `data/history/master_index.jsonl` + `data/history/patterns.md` 作历史同质化与规律加权（**只读历史，不删**）

### 硬剔除（命中任一 → reject）

1. 热度下行（`heat_declining`）
2. 同质化严重（相对历史 kept 标题）
3. 仅行业资讯、无实操空间（`industry_only`）
4. 24h 爆火概率 < 0.35
5. 综合分 < 6.0 且缺实操钩子

### 动作

```bash
python3 scripts/score_filter.py \
  --merged data/archive/YYYY-MM-DD/02_merged.json \
  --out data/archive/YYYY-MM-DD/03_scored.json \
  --top-n 20
```

模型可对 `kept` 做二次精修分数，但**不得**把已 reject 且无新证据的条目强行捞回。  
只保留有**短视频变现潜力**的选题（实操/演示/可跟做）。默认总结 **20** 条。

### 受众铁律（小白/普通人）

- **要**：电脑/手机上就能碰到的工具与场景——修图、剪辑、写作、办公、小红书、提示词、插件/Agent 接管软件（范例：Codex 操作 Photoshop 无损修图）
- **不要**：美中 AI 霸权、全球市场 CAGR、资本开支战争、纯财报股价、国会法案等「老百姓插不上手」的大叙事  
- 配置：`config/audience.yaml` + `score_filter.py`（`too_far` 硬剔；软补齐也禁止 too_far 进池）  
- X 检索词偏向教程/工具/接管/一键（见 `pipeline.yaml` → `x_sources`）

---

## Phase ④ — 标准化内容包（硬规则：按条内容生成）

### 不可妥协

1. **每条选题独立生成**「口播开场钩子」「分步骤实操拍摄流程」「封面标题」「画面参考」  
2. 输入必须是该条的 `title + snapshot_text + source`，**禁止**全站同一模板  
3. **禁止套话**示例（出现即失败）：  
   `停一下——{标题}，我花了半小时实测，结论和热搜完全不是一回事…`  
   `镜头1：封面同款大字 + 结果画面闪现`（若每条都一样）  
4. 同批次内：钩子全文唯一、分镜全序列唯一；由 `scripts/content_plan.py` 的 `ensure_batch_unique` + `validate_unique` 强制；**校验失败则流水线中止**  
5. 实现入口（每次生成必跑，不要跳过）：  
   `scripts/build_packages.py` → 内部调用 `content_plan.analyze_topic`  
6. Agent 若人工改写，也必须**逐条**根据该热点实质改，不得复制粘贴到其它条

对每条 `kept` 必须产出以下字段（缺一不可）：

| 字段 | 说明 |
|---|---|
| 爆款短视频封面标题 | ≤18 字，含本条实体/数字/冲突 |
| 口播开场钩子 | 前 3 秒可播；必须点名本条核心实体或冲突 |
| 分步骤实操拍摄流程 | 分镜列表含秒数；镜头内容绑定本条主题 |
| 推荐视频时长 | 如 60-90秒 |
| 拍摄画面参考 | 与本条题材匹配的构图/录屏要点 |

```bash
python3 scripts/build_packages.py \
  --scored data/archive/YYYY-MM-DD/03_scored.json \
  --out-json data/archive/YYYY-MM-DD/04_packages.json \
  --out-md output/latest/delivery.md \
  --out-csv output/latest/delivery.csv
# 内部：content_plan.analyze_topic → ensure_batch_unique → validate_unique（失败 exit 2）
```

然后 `publish_hub.py` 写入统一预览中心。

---

## Phase ⑤ — 留存规则（永久）

| 路径 | 内容 | 删除？ |
|---|---|---|
| `data/archive/YYYY-MM-DD/*` | 当日全阶段 JSON/MD/CSV | **禁止** |
| `data/history/master_index.jsonl` | 每日 kept 摘要追加 | **禁止清空** |
| `data/history/patterns.md` | 往期优质规律，只追加 | **禁止清空** |
| `output/latest/*` | 最新交付（可覆盖） | 可覆盖 |
| `logs/YYYY-MM-DD.log` | 运行日志 | 禁止主动删 |

后续每日筛选**必须**读取 `master_index.jsonl` 与 `patterns.md` 优化判断。  
**不需要清空历史记录。**

每次 full/enrich 结束后，向 `patterns.md` **追加**一小节：

```markdown
## YYYY-MM-DD
- 今日 kept 共性：...
- 高分维度：...
- 应避免：...
```

---

## 交付格式（最终对用户）

**只输出清晰表格，拒绝冗余废话。**

1. 总表（Markdown）
2. 逐条拍摄方案表
3. 一行路径提示：`output/latest/delivery.md` / `delivery.csv`

不要写长篇方法论、不要重复本 SKILL 说明。

---

## 一键 / 定时

### 手动完整跑

```bash
cd <本项目根> && bash scripts/run_pipeline.sh
```

### 仅脚本层（跳过 Grok 二次 enrich）

```bash
SKIP_GROK=1 bash scripts/run_pipeline.sh
```

### 每日 09:00

- macOS：`launchd/com.qwe.ai-hotspot-pipeline.plist` → `launchctl load`
- 或 Grok scheduler `interval: 1d`（近似日频；**正点 9 点以 launchd 为准**）

定时任务必须 `cwd` 为本项目根，且 `PATH` 含 `uv` 与 `~/.local/bin`。

---

## 状态检查

```bash
ls -lt data/archive | head
tail -5 data/history/master_index.jsonl
wc -l output/latest/delivery.md
```

---

## 失败与降级

| 故障 | 处理 |
|---|---|
| TrendRadar 爬取失败 | 用已有 DB；标注 crawl.ok=false |
| X 工具不可用 | `02_x_raw.json` 空数组，继续，交付表注明「无 X 补充」 |
| 小红书搜不到 | web items 可空，不中止 |
| kept=0 | 仍生成空表 + 写出 rejected top20 原因，便于调关键词 |
| 禁止 | 编造热度/互动数；删除 archive/history；跳过 ① 直接 ④ |

---

## Refusals

- 「跳过 TrendRadar 直接编热点」→ 拒绝
- 「清空历史重新开始」→ 拒绝（可新建分支副本，默认库不删）
- 「只给灵感不要表格」→ 拒绝；最终必须是表
- 「把已剔除的资讯硬塞进交付」→ 拒绝，除非用户显式 override 并记入 note
- 「钩子/分镜用同一模板批量填」→ **拒绝**；必须按条内容生成并过唯一性校验

---

## 与三件工具的契约

| 工具 | 角色 |
|---|---|
| **TrendRadar** | ① 数据源：爬取 + 本地 DB +（可选 MCP 查询） |
| **Grok** | ② X 实时网 + web 补漏 + 文案精修 + Skill 编排 |
| **cheat-on-content** | ③ 评分哲学/维度/硬剔除；本流水线用 `score_filter.py` 可重复实现，并兼容后续人工 `/cheat-predict` |

本 Skill 是**路由器 + 质检清单**；可重复执行的原子步骤在 `scripts/`。
