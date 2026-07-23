#!/usr/bin/env python3
"""Phase 4: 为 kept 选题生成标准化拍摄方案（可被 Skill 精修覆盖）。"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[1]


def cover_title(title: str) -> str:
    t = re.sub(r"\s+", "", title)
    if len(t) > 18:
        t = t[:16] + "…"
    # 封面型：数字/反差优先
    if not re.search(r"\d|！|!|？|\?", t):
        return f"别再错过：{t}"
    return t


def hook(title: str) -> str:
    base = title.rstrip("。.!！?？")
    return (
        f"停一下——{base}，"
        f"我花了半小时实测，结论和热搜完全不是一回事。接下来 60 秒给你可复现步骤。"
    )


def steps(title: str, actionable: bool) -> list[str]:
    if actionable:
        return [
            "镜头1（0-3s）：封面同款大字 + 结果画面闪现，口播钩子原句",
            "镜头2（3-15s）：点明痛点/误区（观众为什么会踩坑）",
            "镜头3（15-45s）：分 3 步实操演示（屏幕录制 + 手指标注）",
            "镜头4（45-70s）：关键参数/提示词/设置特写，可暂停抄",
            "镜头5（70-90s）：前后对比结果 + 适用人群",
            "镜头6（90-end）：一句总结 + 关注引导（下期做进阶）",
        ]
    return [
        "镜头1（0-3s）：争议结论开场，制造认知冲突",
        "镜头2（3-20s）：用 1 个具体案例解释热点本质",
        "镜头3（20-50s）：拆成「是什么→为什么→你能用」三段",
        "镜头4（50-75s）：给 1 个可立刻做的最小行动",
        "镜头5（75-end）：立场收束 + 互动提问",
    ]


def duration(title: str, actionable: bool) -> str:
    if re.search(r"(教程|步骤|工作流|配置|安装)", title):
        return "90-120秒"
    if actionable:
        return "60-90秒"
    return "45-75秒"


def visuals(title: str) -> list[str]:
    refs = [
        "竖屏 9:16，人脸/声音出镜占上 1/3，下 2/3 录屏",
        "关键词大字幕（每屏不超过 10 字）",
        "关键操作处用黄色圆圈/箭头标注",
    ]
    if re.search(r"(绘画|图像|视频|Sora|可灵|即梦)", title, re.I):
        refs.append("结果对比：左 Before / 右 After 分屏")
    if re.search(r"(代码|Cursor|Claude Code|Agent)", title, re.I):
        refs.append("IDE 全屏录制 + 终端输出高亮")
    if re.search(r"(工具|免费|开源)", title):
        refs.append("工具官网/下载页 2 秒建立可信")
    return refs


def package(it: dict) -> dict:
    title = it.get("title") or ""
    return {
        "id": it.get("id"),
        "选题标题": title,
        "爆款封面标题": cover_title(title),
        "口播开场钩子": hook(title),
        "分步骤实操拍摄流程": steps(title, bool(it.get("actionable"))),
        "推荐视频时长": duration(title, bool(it.get("actionable"))),
        "拍摄画面参考": visuals(title),
        "爆火概率_6h": it.get("viral_prob_6h"),
        "爆火概率_24h": it.get("viral_prob_24h"),
        "流量红利剩余时长": f"{it.get('traffic_window_hours')}小时",
        "同行内卷竞争度": it.get("competition_score"),
        "综合分": it.get("composite_score"),
        "维度分": it.get("dimension_scores"),
        "来源平台": it.get("source") or it.get("platform_id"),
        "原始关键词": it.get("keywords") or [],
        "原始链接": it.get("url") or "",
        "热度排名": it.get("heat_rank"),
        "热度增速": it.get("heat_velocity"),
    }


def to_markdown(packages: list[dict], meta: dict) -> str:
    lines = []
    lines.append(f"# AI 热点短视频选题交付表")
    lines.append("")
    lines.append(f"- 生成时间：{meta.get('generated_at')}")
    lines.append(f"- 保留选题：{len(packages)}")
    lines.append(f"- 流水线：TrendRadar → X补充 → cheat筛选 → 标准化脚本")
    lines.append("")
    lines.append("## 总表")
    lines.append("")
    lines.append(
        "| # | 选题 | 封面标题 | 爆火6h | 爆火24h | 红利剩余 | 内卷 | 综合分 | 时长 | 来源 |"
    )
    lines.append("|---:|---|---|---:|---:|---:|---:|---:|---|---|")
    for i, p in enumerate(packages, 1):
        lines.append(
            "| {i} | {t} | {c} | {p6:.0%} | {p24:.0%} | {w} | {comp} | {score} | {dur} | {src} |".format(
                i=i,
                t=(p["选题标题"] or "")[:28],
                c=(p["爆款封面标题"] or "")[:22],
                p6=float(p.get("爆火概率_6h") or 0),
                p24=float(p.get("爆火概率_24h") or 0),
                w=p.get("流量红利剩余时长"),
                comp=p.get("同行内卷竞争度"),
                score=p.get("综合分"),
                dur=p.get("推荐视频时长"),
                src=str(p.get("来源平台") or "")[:20],
            )
        )
    lines.append("")
    lines.append("## 逐条拍摄方案")
    lines.append("")
    for i, p in enumerate(packages, 1):
        lines.append(f"### {i}. {p['选题标题']}")
        lines.append("")
        lines.append(f"| 字段 | 内容 |")
        lines.append(f"|---|---|")
        lines.append(f"| 爆款封面标题 | {p['爆款封面标题']} |")
        lines.append(f"| 口播开场钩子 | {p['口播开场钩子']} |")
        lines.append(f"| 推荐视频时长 | {p['推荐视频时长']} |")
        lines.append(
            f"| 概率/红利/内卷 | 6h={p['爆火概率_6h']} / 24h={p['爆火概率_24h']} / {p['流量红利剩余时长']} / 内卷={p['同行内卷竞争度']} |"
        )
        lines.append(f"| 来源 | {p['来源平台']} |")
        lines.append(f"| 关键词 | {', '.join(p.get('原始关键词') or [])} |")
        lines.append(f"| 链接 | {p.get('原始链接') or '-'} |")
        lines.append("")
        lines.append("**分步骤实操拍摄流程**")
        for s in p.get("分步骤实操拍摄流程") or []:
            lines.append(f"- {s}")
        lines.append("")
        lines.append("**拍摄画面参考**")
        for s in p.get("拍摄画面参考") or []:
            lines.append(f"- {s}")
        lines.append("")
    return "\n".join(lines)


def to_csv(packages: list[dict]) -> str:
    headers = [
        "选题标题",
        "爆款封面标题",
        "口播开场钩子",
        "推荐视频时长",
        "爆火概率_6h",
        "爆火概率_24h",
        "流量红利剩余时长",
        "同行内卷竞争度",
        "综合分",
        "来源平台",
        "原始关键词",
        "原始链接",
        "分步骤实操拍摄流程",
        "拍摄画面参考",
    ]
    import csv
    import io

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    w.writeheader()
    for p in packages:
        row = dict(p)
        row["原始关键词"] = "|".join(p.get("原始关键词") or [])
        row["分步骤实操拍摄流程"] = " || ".join(p.get("分步骤实操拍摄流程") or [])
        row["拍摄画面参考"] = " || ".join(p.get("拍摄画面参考") or [])
        w.writerow(row)
    return buf.getvalue()


def append_master_index(path: Path, meta: dict, packages: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "date": meta.get("date"),
        "generated_at": meta.get("generated_at"),
        "kept_count": len(packages),
        "kept_titles": [p["选题标题"] for p in packages],
        "kept_ids": [p["id"] for p in packages],
        "avg_viral_24h": round(
            sum(float(p.get("爆火概率_24h") or 0) for p in packages) / max(len(packages), 1), 3
        ),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scored", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--master-index", default=str(ROOT / "data/history/master_index.jsonl"))
    args = ap.parse_args()

    scored = json.loads(Path(args.scored).read_text(encoding="utf-8"))
    kept = scored.get("kept") or []
    packages = [package(it) for it in kept]
    now = datetime.now(TZ)
    meta = {
        "phase": 4,
        "date": now.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(),
        "count": len(packages),
    }
    payload = {"meta": meta, "packages": packages}

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = to_markdown(packages, meta)
    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_md).write_text(md, encoding="utf-8")
    # also mirror under archive next to json if path under archive
    arch_md = out_json.parent / "04_delivery.md"
    arch_md.write_text(md, encoding="utf-8")

    Path(args.out_csv).write_text(to_csv(packages), encoding="utf-8")
    append_master_index(Path(args.master_index), meta, packages)
    print(f"[package] {len(packages)} packages → {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
