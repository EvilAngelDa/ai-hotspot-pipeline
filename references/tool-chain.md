# 三件工具契约

| 工具 | 角色 |
|------|------|
| [TrendRadar](https://github.com/sansan0/TrendRadar) | Phase① 多平台热榜爬取与本地库；可选 MCP |
| Grok（X 搜索 + 本 Skill） | Phase② 推特/小红书补漏 + 文案精修 + 编排 |
| [cheat-on-content](https://github.com/XBuilderLAB/cheat-on-content) | Phase③ 评分哲学；本仓库 `score_filter.py` 可重复实现 7 维粗筛 |

## TrendRadar 本地 AI 分析

若出现「未配置 AI API Key」，可将 TrendRadar `config.yaml` 设为：

```yaml
ai:
  model: "local/osint"
  api_key: "local"
```

并使用带 `trendradar/ai/local_backend.py` 的本地补丁版（本 skill 运行时以爬取数据为主，不强制依赖云端分析 Key）。
