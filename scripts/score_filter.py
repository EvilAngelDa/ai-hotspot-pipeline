#!/usr/bin/env python3
"""Phase 3: 粗打分 + 硬剔除。

受众默认：**普通人/小白可触达**（能跟着做的工具与场景）。
坚决压低：美中霸权、资本开支、纯财报股价等「插不上手」叙事。
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

# 小白可跟做 / 日常工具
ACTIONABLE = re.compile(
    r"(怎么|如何|教程|上手|实测|评测|对比|方法|步骤|Prompt|提示词|工具|开源|免费|替代|一键|"
    r"工作流|workflow|指南|安装|配置|玩法|案例|拆解|复现|接管|修图|抠图|去水印|剪辑|"
    r"配音|字幕|写作|办公|Excel|PPT|Word|Photoshop|PS|剪映|小红书|抖音|插件|"
    r"Cursor|Codex|Claude|ChatGPT|豆包|通义|Kimi|Gemini|Grok|保姆级|小白|5分钟|3步)",
    re.I,
)

# 纯行业/资本（无操作）
INDUSTRY_ONLY = re.compile(
    r"(融资|估值|财报|任命|裁员|股价|涨跌|监管约谈|政策解读$|获批|上市|分析师|目标价)",
    re.I,
)

# 离普通人太远：宏大叙事 / 纯资本 / 极客站外长帖硬剔
TOO_FAR = re.compile(
    r"(霸权|中美AI|美中AI|美中|全球AI市场|CAGR|资本开支|capex|军备竞赛|地缘|"
    r"制裁|Kill\s*Switch|国会法案|华尔街|Nasdaq|道指|标普|期货|市值战争|"
    r"统治地位|权力斗争|超级工厂|生态共建中国行业|Harness标准|算力军备|"
    r"芯片军备|全球超powers|AI\s*Dominance|AI\s*hegemony|cash burn|"
    r"price target|stock jumps|sell off|earnings|增资\d|FSD是拉动|"
    r"open-weight AI risks|FLOSS commons|pelicanmaxxing|tokeni[sz]ation|"
    r"Points:\s*\d+|news\.ycombinator|网格智算|林下场景|超级个体|Builder工具|"
    r"商业智能体|行业版Harness|几何、物理AI|累计获超)",
    re.I,
)

# 日常小白加分词（短英文必须 \b，避免 PS 命中 https）
BEGINNER_BOOST = re.compile(
    r"(小白|保姆级|手把手|一键|免费|修图|P图|调色|抠图|去水印|剪映|Photoshop|"
    r"\bPS\b|接管|插件|办公|\bExcel\b|表格|\bPPT\b|周报|简历|翻译|配音|字幕|短视频|"
    r"小红书|抖音|手机|学生|打工人|副业|省时间|5分钟|3步|不会代码|"
    r"\bCursor\b|\bCodex\b|Claude\s*Code|\bChatGPT\b|豆包|通义|\bKimi\b|\bGemini\b|\bGrok\b)",
    re.I,
)

HYPE_OVERUSED = ["颠覆", "炸裂", "一夜暴富", "必看", "史诗级", "彻底改变"]


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
        sa = {nt[i : i + 2] for i in range(len(nt) - 1)}
        sb = {nh[i : i + 2] for i in range(len(nh) - 1)}
        if sa and len(sa & sb) / len(sa | sb) >= 0.65:
            hits += 1
    return min(1.0, hits / 3.0)


def is_too_far(title: str, text: str) -> bool:
    blob = f"{title} {text}"
    if TOO_FAR.search(blob):
        return True
    # 纯宏观财经且无工具动词
    if INDUSTRY_ONLY.search(title) and not ACTIONABLE.search(blob):
        return True
    if re.search(r"(futures|earnings|price target|sell off|capex fear)", blob, re.I):
        if not BEGINNER_BOOST.search(blob):
            return True
    return False


def is_beginner_friendly(title: str, text: str) -> bool:
    """普通人能跟做：日常工具/中文场景/明确教程动作。"""
    blob = f"{title} {text}"
    if is_too_far(title, text):
        return False
    # 纯英文宏大/极客长帖且无日常工具词 → 否
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", title))
    has_daily_tool = bool(
        re.search(
            r"(Photoshop|\bPS\b|剪映|\bExcel\b|\bPPT\b|\bWord\b|小红书|抖音|修图|P图|写作|周报|"
            r"字幕|配音|办公|提示词|\bPrompt\b|\bCursor\b|\bCodex\b|\bChatGPT\b|Claude|豆包|通义|"
            r"\bKimi\b|\bGemini\b|\bGrok\b|插件|接管|一键|小白|教程|怎么用|跟做|无损|P图)",
            blob,
            re.I,
        )
    )
    if BEGINNER_BOOST.search(blob) and (has_cjk or has_daily_tool):
        return True
    if has_daily_tool and ACTIONABLE.search(blob):
        return True
    # 中文跟做语境（避免「我」误匹配「我国」）
    if has_cjk and ACTIONABLE.search(blob) and re.search(
        r"(我用|我的|教你|帮你|帮我|直接让|打开软件|手机端|电脑上|插件|复制提示词|跟着做|小白|不会代码|一键)",
        blob,
    ):
        return True
    return False


def score_item(it: dict, history: list[str]) -> dict:
    title = it.get("title") or ""
    text = it.get("snapshot_text") or title
    heat_rank = it.get("heat_rank")
    vel = float(it.get("heat_velocity") or 0)
    src = it.get("source") or ""
    blob = f"{title} {text}"

    too_far = is_too_far(title, text)
    beginner = is_beginner_friendly(title, text)

    er = 2
    if re.search(r"(震惊|离谱|不敢信|居然|竟然|疯了|崩了|封神|逆天)", title):
        er += 2
    if re.search(r"(你|我|打工人|学生|设计师|运营|自媒体|宝妈|上班)", title):
        er += 1
    if beginner:
        er += 1

    hp = 2
    if len(title) <= 28:
        hp += 1
    if re.search(r"\d+|对比|vs|VS|从.+到|别再|不要|停止|立刻|3步|5分钟|一键|直接", title):
        hp += 2
    if title.endswith("？") or "?" in title or "！" in title or "!" in title:
        hp += 1

    ql = 2
    if re.search(r"[：:].{4,}|「.+」|“.+”", title):
        ql += 1
    if re.search(r"(正确方式|误区|不要|才是|无损|正确打开)", title):
        ql += 2

    na = 2
    if ACTIONABLE.search(blob):
        na += 2
    if re.search(r"(故事|亲历|我用|实测|一天|7天|接管|帮我)", title):
        na += 1

    # AB：普通人广度 — 小白工具加，宏大叙事砍
    ab = 3
    if BEGINNER_BOOST.search(blob):
        ab += 2
    if re.search(r"(ChatGPT|Claude|Cursor|Codex|剪映|PS|Photoshop|豆包|免费)", title, re.I):
        ab += 1
    if too_far:
        ab -= 3
    if re.search(r"(CUDA|kernel|RLHF|MoE|量化训练|论文|Harness|超级工厂)", title, re.I):
        ab -= 2

    sr = 2
    if heat_rank is not None and int(heat_rank) <= 10:
        sr += 1  # 名次权重下调，避免纯热搜宏观占坑
    elif heat_rank is not None and int(heat_rank) <= 30:
        sr += 1
    if beginner:
        sr += 1
    if vel > 0.3:
        sr += 1
    if too_far:
        sr -= 2

    sat = 2
    if re.search(r"(替代|终结|不要把|才是|反向|冷门|无损)", title):
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
    composite = round(sum(dims.values()) / 7 * 2.0, 2)
    if beginner:
        composite = round(min(10.0, composite + 0.8), 2)
    if too_far:
        composite = round(max(0.0, composite - 2.5), 2)

    actionable = bool(ACTIONABLE.search(blob)) or beginner
    industry_only = bool(INDUSTRY_ONLY.search(title)) and not actionable
    homo = homogenization(title, history)
    heat_declining = vel < -0.15 or (heat_rank is not None and int(heat_rank) > 40 and vel <= 0)

    base = composite / 10.0
    rank_boost = 0.0
    if heat_rank is not None:
        rank_boost = max(0.0, (30 - int(heat_rank)) / 30.0) * 0.15  # 弱化纯榜单
    vel_boost = max(-0.15, min(0.2, vel * 0.3))
    action_boost = 0.18 if actionable else -0.2
    beginner_boost = 0.15 if beginner else -0.12
    far_pen = -0.35 if too_far else 0.0
    homo_pen = -0.25 * homo
    p24 = max(
        0.02,
        min(
            0.95,
            base * 0.5
            + rank_boost
            + vel_boost
            + action_boost
            + beginner_boost
            + far_pen
            + homo_pen
            + 0.12,
        ),
    )
    p6 = max(0.01, min(0.9, p24 * (0.55 + max(0, vel) * 0.4)))

    if heat_rank is not None and int(heat_rank) <= 5 and vel >= 0 and beginner:
        remain = 10
    elif beginner:
        remain = 14
    elif heat_declining:
        remain = 3
    else:
        remain = 10

    competition = 4.0
    if heat_rank is not None and int(heat_rank) <= 10:
        competition += 2
    competition += homo * 4
    if re.search(r"(ChatGPT|DeepSeek|Sora|AI绘画)", title, re.I):
        competition += 1.5
    if beginner and re.search(r"(冷门|少有人|正确方式|不要把)", title):
        competition -= 2
    competition = round(max(0.5, min(10.0, competition)), 2)

    reject_reasons = []
    if too_far:
        reject_reasons.append("离普通人太远(宏大叙事/纯资本局)")
    # 硬门槛：必须小白可触达（日常工具/中文可跟做场景）
    if not beginner:
        reject_reasons.append("非小白可触达(缺日常工具/跟做场景)")
    if heat_declining:
        reject_reasons.append("热度下行")
    if industry_only:
        reject_reasons.append("仅行业资讯无实操空间")
    # 小白池放宽同质化：历史 master_index 常含本流水线旧题，避免把好题误杀
    if homo >= (0.92 if beginner else 0.67):
        reject_reasons.append("同质化严重")
    if not actionable:
        reject_reasons.append("缺小白可跟做钩子")
    if p24 < 0.22 and not beginner:
        reject_reasons.append("24h爆火概率过低")
    if composite < 5.0:
        reject_reasons.append("综合分过低")

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
        "beginner_friendly": beginner,
        "too_far": too_far,
        "homogenization": round(homo, 3),
        "heat_declining": heat_declining,
        "industry_only": industry_only,
        "keep": keep,
        "reject_reasons": reject_reasons,
        "scored_under_rubric_version": "beginner-everyday-v1",
    }


def soft_fill_key(x: dict) -> tuple:
    """软补齐时优先小白可触达，绝不优先宏大叙事。"""
    return (
        0 if x.get("too_far") else 1,
        1 if x.get("beginner_friendly") else 0,
        1 if x.get("actionable") else 0,
        x.get("viral_prob_24h") or 0,
        x.get("composite_score") or 0,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--master-index", default=str(ROOT / "data/history/master_index.jsonl"))
    args = ap.parse_args()

    blob = json.loads(Path(args.merged).read_text(encoding="utf-8"))
    items = blob.get("items") or []
    history = load_history_titles(Path(args.master_index))

    scored = [score_item(it, history) for it in items]
    hard_kept = [x for x in scored if x["keep"] and not x.get("too_far")]
    hard_kept.sort(key=soft_fill_key, reverse=True)

    kept = list(hard_kept[: args.top_n])
    if len(kept) < args.top_n:
        hard_ids = {x.get("id") for x in kept}
        # 软补：禁止 too_far 进池
        # 软补也只从 beginner 池取，绝不回填霸权/财报/纯英文极客帖
        pool = [
            x
            for x in scored
            if x.get("id") not in hard_ids
            and not x.get("too_far")
            and x.get("beginner_friendly")
        ]
        pool.sort(key=soft_fill_key, reverse=True)
        for x in pool:
            if len(kept) >= args.top_n:
                break
            y = dict(x)
            y["keep"] = True
            y["soft_fill"] = True
            reasons = list(y.get("reject_reasons") or [])
            if "软补齐进总结(小白优先池)" not in reasons:
                reasons.append("软补齐进总结(小白优先池)")
            y["reject_reasons"] = reasons
            kept.append(y)

    kept_ids = {x.get("id") for x in kept}
    rejected = [x for x in scored if x.get("id") not in kept_ids]
    rejected.sort(key=lambda x: x.get("composite_score") or 0, reverse=True)

    now = datetime.now(TZ)
    out = {
        "phase": 3,
        "generated_at": now.isoformat(),
        "audience": "beginner_everyday",
        "counts": {
            "input": len(items),
            "kept": len(kept),
            "hard_kept": len(hard_kept),
            "soft_fill": sum(1 for x in kept if x.get("soft_fill")),
            "too_far_rejected": sum(1 for x in scored if x.get("too_far")),
            "beginner_in_kept": sum(1 for x in kept if x.get("beginner_friendly")),
            "rejected": len(rejected),
            "top_n": args.top_n,
        },
        "kept": kept,
        "rejected": rejected[:80],
        "all_scored": scored,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"[score] audience=beginner_everyday in={len(items)} kept={len(kept)} "
        f"beginner={out['counts']['beginner_in_kept']} too_far={out['counts']['too_far_rejected']} → {out_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
