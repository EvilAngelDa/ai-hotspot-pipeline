#!/usr/bin/env python3
"""Phase 3: cheat-on-content 风格 7 维粗打分 + 爆火/红利/内卷估计 + 硬剔除。

说明：
- 这是可重复的规则化粗筛（对齐 opinion-video-zero 维度名）
- Skill 执行时可用模型对 top 候选做二次精修，但本脚本保证无模型也能产出稳定表
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[1]

ACTIONABLE = re.compile(
    r"(怎么|如何|教程|上手|实测|评测|对比|方法|步骤|Prompt|提示词|工具|开源|免费|替代|一键|工作流|workflow|指南|安装|配置|玩法|案例|拆解|复现)",
    re.I,
)
INDUSTRY_ONLY = re.compile(
    r"(融资|估值|财报|任命|裁员|股价|涨跌|监管约谈|政策解读$|获批|上市)",
    re.I,
)
HYPE_OVERUSED = [
    "颠覆",
    "炸裂",
    "一夜暴富",
    "必看",
    "史诗级",
    "彻底改变",
]


def clamp(n, lo=0, hi=5):
    return max(lo, min(hi, int(round(n))))


def load_history_titles(master_index: Path) -> list[str]:
    if not master_index.exists():
        return []
    titles = []
    for line in master_index.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if row.get("title"):
                titles.append(row["title"])
            for t in row.get("kept_titles") or []:
                titles.append(t)
        except Exception:
            continue
    return titles[-2000:]


def homogenization(title: str, history: list[str]) -> float:
    """0=独特, 1=高度同质。"""
    nt = re.sub(r"\s+", "", title.lower())
    if not nt:
        return 0.5
    hits = 0
    for h in history:
        nh = re.sub(r"\s+", "", h.lower())
        if not nh:
            continue
        if nt in nh or nh in nt:
            hits += 1
            continue
        # token overlap rough
        sa, sb = set(nt[i : i + 2] for i in range(len(nt) - 1)), set(nh[i : i + 2] for i in range(len(nh) - 1))
        if sa and len(sa & sb) / len(sa | sb) >= 0.65:
            hits += 1
    return min(1.0, hits / 3.0)


def score_item(it: dict, history: list[str]) -> dict:
    title = it.get("title") or ""
    text = it.get("snapshot_text") or title
    heat_rank = it.get("heat_rank")
    vel = float(it.get("heat_velocity") or 0)
    src = it.get("source") or ""

    # --- 7 dims 0-5 ---
    # ER: emotional / curiosity
    er = 2
    if re.search(r"(震惊|离谱|不敢信|居然|竟然|疯了|崩了|封神|逆天)", title):
        er += 2
    if re.search(r"(你|我|打工人|创业|学生|程序员|设计师)", title):
        er += 1

    # HP: hook — short punchy or number/contrast
    hp = 2
    if len(title) <= 22:
        hp += 1
    if re.search(r"\d+|对比|vs|VS|从.+到|别再|停止|立刻|3步|5分钟", title):
        hp += 2
    if title.endswith("？") or "?" in title:
        hp += 1

    # QL: quotable
    ql = 2
    if re.search(r"[：:].{4,}|「.+」|“.+”", title):
        ql += 1
    if re.search(r"(本质|底层|真相|误区|正确打开方式)", title):
        ql += 2

    # NA: narrativity potential for short video
    na = 2
    if ACTIONABLE.search(title) or ACTIONABLE.search(text):
        na += 2
    if re.search(r"(故事|亲历|我用|实测|一天|7天)", title):
        na += 1

    # AB: audience breadth for AI short video
    ab = 3
    if re.search(r"(ChatGPT|Claude|DeepSeek|Cursor|Sora|AI绘画|AI视频|免费)", title, re.I):
        ab += 1
    if re.search(r"(CUDA|kernel|RLHF|MoE|量化训练|论文)", title, re.I):
        ab -= 2  # too niche for mass short video

    # SR: social resonance / trend alignment
    sr = 2
    if heat_rank is not None and int(heat_rank) <= 10:
        sr += 2
    elif heat_rank is not None and int(heat_rank) <= 30:
        sr += 1
    if "x:" in src or "twitter" in src or src.startswith("x"):
        sr += 1  # emerging global signal
    if vel > 0.3:
        sr += 1

    # SAT: novelty / twist (not pure satire for AI tools)
    sat = 2
    if re.search(r"(替代|终结|杀死|再见|打脸|反向|冷门)", title):
        sat += 2
    if any(h in title for h in HYPE_OVERUSED):
        sat -= 1

    dims = {
        "ER": clamp(er),
        "HP": clamp(hp),
        "QL": clamp(ql),
        "NA": clamp(na),
        "AB": clamp(ab),
        "SR": clamp(sr),
        "SAT": clamp(sat),
    }
    composite = round(sum(dims.values()) / 7 * 2.0, 2)  # 0-10

    # actionable / industry filter flags
    actionable = bool(ACTIONABLE.search(title) or ACTIONABLE.search(text))
    industry_only = bool(INDUSTRY_ONLY.search(title)) and not actionable
    homo = homogenization(title, history)

    # heat declining: negative velocity with mid/low rank
    heat_declining = vel < -0.15 or (heat_rank is not None and int(heat_rank) > 40 and vel <= 0)

    # viral probs (heuristic calibrated for short-video AI niche)
    base = composite / 10.0
    rank_boost = 0.0
    if heat_rank is not None:
        rank_boost = max(0.0, (30 - int(heat_rank)) / 30.0) * 0.25
    vel_boost = max(-0.15, min(0.2, vel * 0.3))
    action_boost = 0.12 if actionable else -0.18
    homo_pen = -0.25 * homo
    p24 = max(0.02, min(0.95, base * 0.55 + rank_boost + vel_boost + action_boost + homo_pen + 0.1))
    p6 = max(0.01, min(0.9, p24 * (0.55 + max(0, vel) * 0.4)))

    # remaining traffic window (hours)
    if heat_rank is not None and int(heat_rank) <= 5 and vel >= 0:
        remain = 6
    elif heat_rank is not None and int(heat_rank) <= 15 and vel >= 0:
        remain = 12
    elif vel > 0.2:
        remain = 18
    elif heat_declining:
        remain = 3
    else:
        remain = 10
    if "x:" in src or src.startswith("x") or "twitter" in src:
        remain = max(remain, 14)  # emerging global topics last longer cross-platform

    # competition 0-10
    competition = 4.0
    if heat_rank is not None and int(heat_rank) <= 10:
        competition += 3
    competition += homo * 4
    if re.search(r"(ChatGPT|DeepSeek|Sora|AI绘画)", title, re.I):
        competition += 1.5
    if actionable and re.search(r"(冷门|小众|新功能|隐藏|少有人)", title):
        competition -= 2
    competition = round(max(0.5, min(10.0, competition)), 2)

    # reject rules
    reject_reasons = []
    if heat_declining:
        reject_reasons.append("热度下行")
    if industry_only:
        reject_reasons.append("仅行业资讯无实操空间")
    if homo >= 0.67:
        reject_reasons.append("同质化严重")
    if not actionable and composite < 7.0:
        reject_reasons.append("短视频变现潜力不足(缺实操钩子)")
    if p24 < 0.35:
        reject_reasons.append("24h爆火概率过低")
    if composite < 6.0:
        reject_reasons.append("综合分<6")

    keep = len(reject_reasons) == 0

    return {
        **it,
        "dimension_scores": dims,
        "composite_score": composite,
        "viral_prob_6h": round(p6, 3),
        "viral_prob_24h": round(p24, 3),
        "traffic_window_hours": remain,
        "competition_score": competition,
        "actionable": actionable,
        "homogenization": round(homo, 3),
        "heat_declining": heat_declining,
        "industry_only": industry_only,
        "keep": keep,
        "reject_reasons": reject_reasons,
        "scored_under_rubric_version": "opinion-video-zero+ai-shortvideo-v1",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--top-n", type=int, default=8)
    ap.add_argument("--master-index", default=str(ROOT / "data/history/master_index.jsonl"))
    args = ap.parse_args()

    blob = json.loads(Path(args.merged).read_text(encoding="utf-8"))
    items = blob.get("items") or []
    history = load_history_titles(Path(args.master_index))

    scored = [score_item(it, history) for it in items]
    kept = [x for x in scored if x["keep"]]
    kept.sort(key=lambda x: (x["viral_prob_24h"], x["composite_score"]), reverse=True)
    kept = kept[: args.top_n]
    rejected = [x for x in scored if not x["keep"]]
    rejected.sort(key=lambda x: x["composite_score"], reverse=True)

    now = datetime.now(TZ)
    out = {
        "phase": 3,
        "generated_at": now.isoformat(),
        "counts": {
            "input": len(items),
            "kept": len(kept),
            "rejected": len(rejected),
        },
        "kept": kept,
        "rejected": rejected[:50],  # cap for readability
        "all_scored": scored,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[score] in={len(items)} kept={len(kept)} rejected={len(rejected)} → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
