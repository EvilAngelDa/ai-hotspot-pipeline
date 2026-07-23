#!/usr/bin/env python3
"""Phase 2 helper: merge TrendRadar + X(+web) items, dedupe, write 02_merged.json."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[1]


def stable_id(source: str, title: str, url: str = "") -> str:
    norm = re.sub(r"\s+", "", (title or "").lower())
    raw = f"{source}|{norm}|{(url or '').split('?')[0]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def normalize_title(t: str) -> str:
    t = t.lower()
    t = re.sub(r"[\s\|\-_/\\·•,，。!！?？:：;；\"'“”‘’\[\]\(\)（）#@]+", "", t)
    return t


def near_dup(a: str, b: str) -> bool:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # substring containment for short titles
    if len(na) >= 8 and len(nb) >= 8:
        if na in nb or nb in na:
            return True
    # jaccard on char bigrams
    def bigrams(s):
        return {s[i : i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}

    ba, bb = bigrams(na), bigrams(nb)
    inter = len(ba & bb)
    union = len(ba | bb) or 1
    return inter / union >= 0.72


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def as_items(blob) -> list[dict]:
    if isinstance(blob, list):
        return blob
    if isinstance(blob, dict):
        return blob.get("items") or blob.get("data") or []
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trendradar", required=True)
    ap.add_argument("--x", default="")
    ap.add_argument("--web", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    now = datetime.now(TZ)
    sources = []
    for label, path in (
        ("trendradar", args.trendradar),
        ("x", args.x),
        ("web", args.web),
    ):
        if not path:
            continue
        p = Path(path)
        if not p.exists():
            print(f"[merge] skip missing {label}: {path}", file=sys.stderr)
            continue
        items = as_items(load_json(p))
        for it in items:
            it = dict(it)
            it.setdefault("source", label)
            it.setdefault("title", it.get("text") or it.get("name") or "")
            it.setdefault("url", it.get("url") or "")
            it.setdefault("id", stable_id(it["source"], it["title"], it.get("url", "")))
            it.setdefault("snapshot_text", it["title"])
            it.setdefault("snapshot_at", now.isoformat())
            sources.append(it)

    # exact id dedupe + near-title dedupe
    kept: list[dict] = []
    for it in sources:
        if any(x["id"] == it["id"] for x in kept):
            continue
        if any(near_dup(x["title"], it["title"]) for x in kept):
            # keep higher heat / earlier rank
            continue
        kept.append(it)

    out = {
        "phase": 2,
        "generated_at": now.isoformat(),
        "input_counts": {
            "raw": len(sources),
            "merged": len(kept),
        },
        "items": kept,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[merge] {len(sources)} → {len(kept)} → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
