#!/usr/bin/env python3
"""兼容入口：重跑「按条内容生成钩子/分镜」。

主路径已并入 build_packages.py + content_plan.py。
本脚本用于对已有 04_packages.json 强制重生成（不改分数字段）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from content_plan import analyze_topic, ensure_batch_unique, validate_unique  # noqa: E402
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packages", required=True)
    ap.add_argument("--scored", default="")
    ap.add_argument("--out-json", default="")
    ap.add_argument("--out-md", default=str(ROOT / "output/latest/delivery.md"))
    ap.add_argument("--out-csv", default=str(ROOT / "output/latest/delivery.csv"))
    args = ap.parse_args()

    pkg_path = Path(args.packages)
    data = json.loads(pkg_path.read_text(encoding="utf-8"))
    packages = data.get("packages") or []

    snap = {}
    if args.scored and Path(args.scored).exists():
        scored = json.loads(Path(args.scored).read_text(encoding="utf-8"))
        for it in scored.get("kept") or []:
            if it.get("id"):
                snap[it["id"]] = it.get("snapshot_text") or ""
            if it.get("title"):
                snap[it["title"]] = it.get("snapshot_text") or ""

    plans, titles = [], []
    for p in packages:
        title = p.get("选题标题") or ""
        sid = p.get("id")
        snapshot = p.get("snapshot_text") or snap.get(sid) or snap.get(title) or ""
        src = str(p.get("来源平台") or "")
        plan = analyze_topic(title, snapshot, src)
        plans.append(plan)
        titles.append(title)

    plans = ensure_batch_unique(plans, titles)
    for p, plan in zip(packages, plans):
        p.update(plan)

    ok, msg = validate_unique(packages)
    if not ok:
        print(f"[personalize][FATAL] {msg}", file=sys.stderr)
        return 2

    data["packages"] = packages
    out_json = Path(args.out_json) if args.out_json else pkg_path
    out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    spec = importlib.util.spec_from_file_location("bp", ROOT / "scripts" / "build_packages.py")
    bp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bp)
    md = bp.to_markdown(packages, data.get("meta") or {})
    Path(args.out_md).write_text(md, encoding="utf-8")
    Path(args.out_csv).write_text(bp.to_csv(packages), encoding="utf-8")
    arch = pkg_path.parent
    (arch / "04_delivery.md").write_text(md, encoding="utf-8")
    (arch / "04_delivery.csv").write_text(bp.to_csv(packages), encoding="utf-8")

    print(f"[personalize] {len(packages)} ok — {msg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
