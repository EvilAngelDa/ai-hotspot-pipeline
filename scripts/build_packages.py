#!/usr/bin/env python3
"""Phase 4: 为 kept 选题生成标准化拍摄方案。

硬规则（每次必执行）：
- 口播钩子 / 分镜必须按「本条 title + snapshot」内容生成
- 禁止全站同一套话模板
- 批次内钩子、分镜全序列必须唯一，否则校验失败退出
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 同目录模块
sys.path.insert(0, str(Path(__file__).resolve().parent))
from content_plan import analyze_topic, ensure_batch_unique, validate_unique  # noqa: E402

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[1]


def package(it: dict) -> dict:
    title = it.get("title") or ""
    snap = it.get("snapshot_text") or ""
    src = str(it.get("source") or it.get("platform_id") or "")
    plan = analyze_topic(title, snap, src)
    return {
        "id": it.get("id"),
        "选题标题": title,
        "爆款封面标题": plan["爆款封面标题"],
        "口播开场钩子": plan["口播开场钩子"],
        "分步骤实操拍摄流程": plan["分步骤实操拍摄流程"],
        "推荐视频时长": plan["推荐视频时长"],
        "拍摄画面参考": plan["拍摄画面参考"],
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
        "snapshot_text": snap,
        "soft_fill": it.get("soft_fill", False),
    }


def to_markdown(packages: list[dict], meta: dict) -> str:
    lines = [
        "# AI 热点短视频选题交付表",
        "",
        f"- 生成时间：{meta.get('generated_at')}",
        f"- 保留选题：{len(packages)}",
        f"- 流水线：TrendRadar → X补充 → cheat筛选 → **按条内容生成钩子/分镜**",
        "",
        "## 总表",
        "",
        "| # | 选题 | 封面标题 | 爆火6h | 爆火24h | 红利剩余 | 内卷 | 综合分 | 时长 | 来源 |",
        "|---:|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for i, p in enumerate(packages, 1):
        try:
            p6 = f"{float(p.get('爆火概率_6h') or 0):.0%}"
        except Exception:
            p6 = str(p.get("爆火概率_6h"))
        try:
            p24 = f"{float(p.get('爆火概率_24h') or 0):.0%}"
        except Exception:
            p24 = str(p.get("爆火概率_24h"))
        lines.append(
            "| {i} | {t} | {c} | {p6} | {p24} | {w} | {comp} | {score} | {dur} | {src} |".format(
                i=i,
                t=(p.get("选题标题") or "")[:28],
                c=(p.get("爆款封面标题") or "")[:22],
                p6=p6,
                p24=p24,
                w=p.get("流量红利剩余时长"),
                comp=p.get("同行内卷竞争度"),
                score=p.get("综合分"),
                dur=p.get("推荐视频时长"),
                src=str(p.get("来源平台") or "")[:20],
            )
        )
    lines += ["", "## 逐条拍摄方案", ""]
    for i, p in enumerate(packages, 1):
        lines += [
            f"### {i}. {p.get('选题标题')}",
            "",
            "| 字段 | 内容 |",
            "|---|---|",
            f"| 爆款封面标题 | {p.get('爆款封面标题')} |",
            f"| 口播开场钩子 | {p.get('口播开场钩子')} |",
            f"| 推荐视频时长 | {p.get('推荐视频时长')} |",
            f"| 概率/红利/内卷 | 6h={p.get('爆火概率_6h')} / 24h={p.get('爆火概率_24h')} / {p.get('流量红利剩余时长')} / 内卷={p.get('同行内卷竞争度')} |",
            f"| 来源 | {p.get('来源平台')} |",
            f"| 关键词 | {', '.join(p.get('原始关键词') or [])} |",
            f"| 链接 | {p.get('原始链接') or '-'} |",
            "",
            "**分步骤实操拍摄流程**",
        ]
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
        "kept_ids": [p.get("id") for p in packages],
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

    # 批次唯一性：规则引擎二次改写
    plans = [
        {
            "爆款封面标题": p["爆款封面标题"],
            "口播开场钩子": p["口播开场钩子"],
            "分步骤实操拍摄流程": p["分步骤实操拍摄流程"],
            "推荐视频时长": p["推荐视频时长"],
            "拍摄画面参考": p["拍摄画面参考"],
        }
        for p in packages
    ]
    titles = [p["选题标题"] for p in packages]
    uniq_plans = ensure_batch_unique(plans, titles)
    for p, plan in zip(packages, uniq_plans):
        p.update(plan)

    ok, msg = validate_unique(packages)
    if not ok:
        print(f"[package][FATAL] 内容唯一性校验失败: {msg}", file=sys.stderr)
        return 2
    print(f"[package] uniqueness OK ({len(packages)} items) — {msg}")

    now = datetime.now(TZ)
    meta = {
        "phase": 4,
        "date": now.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(),
        "count": len(packages),
        "content_plan": "content_plan.analyze_topic+ensure_batch_unique",
    }
    payload = {"meta": meta, "packages": packages}

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = to_markdown(packages, meta)
    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_md).write_text(md, encoding="utf-8")
    (out_json.parent / "04_delivery.md").write_text(md, encoding="utf-8")
    Path(args.out_csv).write_text(to_csv(packages), encoding="utf-8")
    append_master_index(Path(args.master_index), meta, packages)
    print(f"[package] {len(packages)} packages → {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
