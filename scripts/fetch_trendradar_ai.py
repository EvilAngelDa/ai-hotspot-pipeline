#!/usr/bin/env python3
"""Phase 1: 触发 TrendRadar 爬取并导出近 lookback_hours 的 AI 相关热点。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import yaml
except ImportError:
    yaml = None

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml:
        return yaml.safe_load(text)
    # minimal fallback for simple keys we need
    raise SystemExit("PyYAML required: pip install pyyaml  or use project venv")


def load_keywords(path: Path) -> list[str]:
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        words.append(line)
    return words


def is_ai_related(title: str, keywords: list[str]) -> bool:
    t = title.lower()
    for kw in keywords:
        if kw.lower() in t:
            return True
    # extra pattern for standalone AI token
    if re.search(r"(?<![a-z])ai(?![a-z])", t, re.I):
        return True
    return False


def stable_id(source: str, title: str, url: str = "") -> str:
    norm = re.sub(r"\s+", "", title.lower())
    raw = f"{source}|{norm}|{url.split('?')[0] if url else ''}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def parse_crawl_time(date_str: str, crawl_time: str) -> datetime | None:
    """date_str=YYYY-MM-DD, crawl_time=HH-MM or full timestamp."""
    try:
        if re.match(r"^\d{2}-\d{2}$", crawl_time or ""):
            hh, mm = crawl_time.split("-")
            return datetime(
                int(date_str[:4]),
                int(date_str[5:7]),
                int(date_str[8:10]),
                int(hh),
                int(mm),
                tzinfo=TZ,
            )
        if " " in (crawl_time or ""):
            dt = datetime.strptime(crawl_time[:19], "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=TZ)
    except Exception:
        return None
    return None


def trigger_crawl(project_root: Path) -> dict:
    cmd = ["uv", "run", "python", "-m", "trendradar"]
    try:
        p = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=300,
            env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PATH": __import__("os").environ.get("PATH", "") + ":/Users/qwe/.local/bin"},
        )
        return {
            "ok": p.returncode == 0,
            "returncode": p.returncode,
            "stdout_tail": (p.stdout or "")[-2000:],
            "stderr_tail": (p.stderr or "")[-1000:],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def fetch_from_db(
    project_root: Path,
    platforms: list[str],
    keywords: list[str],
    lookback_hours: int,
    max_per_platform: int,
) -> list[dict]:
    news_dir = project_root / "output" / "news"
    if not news_dir.exists():
        return []

    now = datetime.now(TZ)
    cutoff = now - timedelta(hours=lookback_hours)
    items: list[dict] = []

    # scan recent db files (today + yesterday for night-edge)
    for db_path in sorted(news_dir.glob("*.db"), reverse=True)[:3]:
        date_str = db_path.stem  # YYYY-MM-DD
        try:
            con = sqlite3.connect(str(db_path))
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            # join rank history for heat velocity proxy
            rows = cur.execute(
                """
                SELECT n.id, n.title, n.platform_id, n.rank, n.url, n.mobile_url,
                       n.first_crawl_time, n.last_crawl_time, n.crawl_count,
                       n.created_at, n.updated_at
                FROM news_items n
                WHERE n.platform_id IN ({placeholders})
                ORDER BY n.rank ASC
                """.format(
                    placeholders=",".join("?" * len(platforms))
                ),
                platforms,
            ).fetchall()

            per_platform_count: dict[str, int] = {}
            for r in rows:
                pid = r["platform_id"]
                if per_platform_count.get(pid, 0) >= max_per_platform:
                    continue
                title = r["title"] or ""
                if not is_ai_related(title, keywords):
                    continue

                ts = parse_crawl_time(date_str, r["last_crawl_time"] or r["first_crawl_time"] or "")
                if ts is None:
                    # fallback created_at
                    try:
                        ts = datetime.strptime(str(r["created_at"])[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
                    except Exception:
                        ts = now
                if ts < cutoff:
                    continue

                # rank history for velocity
                hist = cur.execute(
                    "SELECT rank, crawl_time FROM rank_history WHERE news_item_id=? ORDER BY id",
                    (r["id"],),
                ).fetchall()
                ranks = [h["rank"] for h in hist] if hist else [r["rank"]]
                heat_velocity = 0.0
                if len(ranks) >= 2:
                    # rank 变小 = 上升；用 (old-new)/old
                    old, new = ranks[0], ranks[-1]
                    heat_velocity = (old - new) / max(old, 1)
                else:
                    # 单次快照：用名次反推热度分
                    heat_velocity = max(0.0, (50 - int(r["rank"])) / 50.0)

                interaction_proxy = {
                    "rank": int(r["rank"]),
                    "crawl_count": int(r["crawl_count"] or 1),
                    "rank_history": ranks[-5:],
                }

                items.append(
                    {
                        "id": stable_id(f"trendradar:{pid}", title, r["url"] or ""),
                        "title": title,
                        "source": f"trendradar:{pid}",
                        "platform_id": pid,
                        "url": r["url"] or r["mobile_url"] or "",
                        "published_at": ts.isoformat(),
                        "keywords": [kw for kw in keywords if kw.lower() in title.lower()][:5],
                        "heat_rank": int(r["rank"]),
                        "heat_velocity": round(heat_velocity, 4),
                        "interaction": interaction_proxy,
                        "snapshot_text": title,
                        "snapshot_at": now.isoformat(),
                    }
                )
                per_platform_count[pid] = per_platform_count.get(pid, 0) + 1
            con.close()
        except Exception as e:
            print(f"[warn] db {db_path}: {e}", file=sys.stderr)

    # RSS tech
    rss_dir = project_root / "output" / "rss"
    for db_path in sorted(rss_dir.glob("*.db"), reverse=True)[:2] if rss_dir.exists() else []:
        try:
            con = sqlite3.connect(str(db_path))
            con.row_factory = sqlite3.Row
            tables = [t[0] for t in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            # try common table names
            for table in tables:
                cols = [c[1] for c in con.execute(f"PRAGMA table_info({table})").fetchall()]
                if "title" not in cols:
                    continue
                colset = set(cols)
                select_cols = ["title"]
                for c in ("url", "link", "feed_id", "source", "published", "published_at", "created_at", "summary"):
                    if c in colset:
                        select_cols.append(c)
                q = f"SELECT {', '.join(select_cols)} FROM {table} LIMIT 200"
                for r in con.execute(q):
                    title = r["title"] or ""
                    if not is_ai_related(title, keywords):
                        continue
                    url = ""
                    for k in ("url", "link"):
                        if k in colset:
                            url = r[k] or ""
                            break
                    feed = r["feed_id"] if "feed_id" in colset else (r["source"] if "source" in colset else "rss")
                    items.append(
                        {
                            "id": stable_id(f"trendradar:rss:{feed}", title, url),
                            "title": title,
                            "source": f"trendradar:rss:{feed}",
                            "platform_id": f"rss:{feed}",
                            "url": url,
                            "published_at": now.isoformat(),
                            "keywords": [kw for kw in keywords if kw.lower() in title.lower()][:5],
                            "heat_rank": None,
                            "heat_velocity": 0.2,
                            "interaction": {"type": "rss"},
                            "snapshot_text": (r["summary"] if "summary" in colset else title) or title,
                            "snapshot_at": now.isoformat(),
                        }
                    )
                break
            con.close()
        except Exception as e:
            print(f"[warn] rss {db_path}: {e}", file=sys.stderr)

    # dedupe by id
    seen = set()
    unique = []
    for it in items:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        unique.append(it)
    return unique


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config" / "pipeline.yaml"))
    ap.add_argument("--out", default="")
    ap.add_argument("--skip-crawl", action="store_true")
    args = ap.parse_args()

    cfg = load_yaml(Path(args.config))
    keywords = load_keywords(ROOT / "config" / "ai_keywords.txt")
    tr = cfg["trendradar"]
    import os
    raw_root = tr.get("project_root") or os.environ.get("TRENDRADAR_ROOT") or str(Path.home() / "tools" / "TrendRadar")
    # expand ${VAR:-default} lightly + env + ~
    if "${TRENDRADAR_ROOT" in str(raw_root) or "$HOME" in str(raw_root) or "$" in str(raw_root):
        raw_root = os.path.expandvars(str(raw_root).replace("${TRENDRADAR_ROOT:-$HOME/tools/TrendRadar}", os.environ.get("TRENDRADAR_ROOT") or str(Path.home() / "tools" / "TrendRadar")))
    project_root = Path(os.path.expanduser(str(raw_root))).resolve()
    lookback = int(cfg.get("lookback_hours", 12))
    platforms = [p["id"] for p in tr["platforms"]]
    max_per = int(tr.get("max_items_per_platform", 80))

    now = datetime.now(TZ)
    date = now.strftime("%Y-%m-%d")
    out_path = Path(args.out) if args.out else ROOT / f"data/archive/{date}/01_trendradar.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    crawl_result = None
    if tr.get("trigger_crawl_before_fetch", True) and not args.skip_crawl:
        print("[phase1] triggering TrendRadar crawl...")
        crawl_result = trigger_crawl(project_root)
        print(f"[phase1] crawl ok={crawl_result.get('ok')}")

    print("[phase1] exporting AI-related hotspots from DB...")
    items = fetch_from_db(project_root, platforms, keywords, lookback, max_per)

    payload = {
        "phase": 1,
        "generated_at": now.isoformat(),
        "lookback_hours": lookback,
        "platforms": platforms,
        "keyword_count": len(keywords),
        "crawl": crawl_result,
        "count": len(items),
        "items": items,
        "notes": {
            "xiaohongshu": "TrendRadar 无小红书源；Phase1.5 由 Skill 用 web_search 补充",
            "interaction": "公开热榜无完整互动数；用 rank + rank_history 作代理指标",
        },
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[phase1] wrote {len(items)} items → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
