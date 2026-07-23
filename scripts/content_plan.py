#!/usr/bin/env python3
"""
内容方案引擎（规则层，每次生成必跑）

硬性规则：
1. 每条选题的「口播开场钩子」「分步骤实操拍摄流程」必须基于该条 title + snapshot 独立生成
2. 禁止全站共用「停一下——{标题}，我花了半小时实测…」一类套话
3. 同一次批次内：钩子全文唯一、分镜全序列唯一；不唯一则强制二次改写
4. 专用路由（高置信实体）优先；否则走内容解析启发式

被 build_packages / personalize_packages 共同引用。
"""
from __future__ import annotations

import hashlib
import re
from typing import Any


STOP = {
    "如何", "怎么", "什么", "一个", "我们", "他们", "以及", "或者", "这个", "那个",
    "进行", "通过", "可以", "已经", "因为", "所以", "如果", "还是", "不是", "就是",
    "the", "and", "for", "with", "from", "that", "this", "will", "have", "been",
}


def _has(text: str, *kws: str) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in kws)


def extract_entities(title: str, snapshot: str = "") -> list[str]:
    text = f"{title} {snapshot or ''}"
    # Prefer multi-token product names first
    multi = re.findall(
        r"Kimi\s*K\d+|DeepSeek|GPT-?[\d\.]+|Claude\s*Opus\s*\d*|OpenAI|Gemini|ChatGPT|Hugging\s*Face|"
        r"OpenClaw|Harness|Agent|MCP|Qwen[\d\.]*|Claude\s*Code|Cursor|Sora|"
        r"小红书|点点|剪映|脸萌|华为|昇腾",
        text,
        re.I,
    )
    # English products / codes
    eng = re.findall(r"\b[A-Za-z][A-Za-z0-9][\w\.\-\+]{1,28}\b", text)
    # Chinese chunks
    zh = re.findall(r"[\u4e00-\u9fff]{2,10}", text)
    # Prefer percents / multi-digit meaningful numbers; skip bare 1-digit
    nums = re.findall(r"\d+(?:\.\d+)?%|\d{2,}x|\d+倍|\d+亿|\d+万|\$\d+|\d{2,}", text, re.I)
    out: list[str] = []
    for e in multi + nums + eng + zh:
        e2 = re.sub(r"\s+", " ", e).strip()
        if not e2 or e2.lower() in STOP or e2 in STOP:
            continue
        if len(e2) == 1 and e2.isdigit():
            continue
        if e2 not in out:
            out.append(e2)
    return out[:12]


def detect_genre(title: str, snapshot: str = "") -> str:
    t = f"{title} {snapshot}"
    rules = [
        ("tutorial", r"教程|怎么装|怎么跑|怎么用|步骤|复现|安装|配置|上手|跟做|CLI|开权"),
        ("review", r"评测|对比|对标|vs|VS|实测|横评|验收"),
        ("controversy", r"争议|评价|到底|真相|作弊|逃逸|蒸馏|站队|吵"),
        ("privacy", r"隐私|照片|视频发给|不要随意|泄露|打码"),
        ("workflow", r"工作流|流水线|MCP|Agent|自动化|GitHub Actions|起号"),
        ("product", r"发布|上线|开源|开权|助手|产品|CEO|专访|对话"),
        ("finance", r"财报|融资|增资|股价|futures|earnings|利润|指引|Nasdaq|capex"),
        ("policy", r"法案|监管|Kill Switch|政策|合规"),
        ("news_brief", r"晚报|热搜|合作|增资|FSD"),
    ]
    for name, pat in rules:
        if re.search(pat, t, re.I):
            return name
    return "explain"


def analyze_topic(title: str, snapshot: str = "", source: str = "") -> dict[str, Any]:
    """为单条选题生成完整拍摄方案（始终内容相关）。"""
    title = (title or "").strip()
    snapshot = (snapshot or "").strip()
    ents = extract_entities(title, snapshot)
    core = ents[0] if ents else (title[:10] or "这个热点")
    core2 = ents[1] if len(ents) > 1 else (ents[0] if ents else "关键点")
    num = next((e for e in ents if re.search(r"\d", e)), "")
    genre = detect_genre(title, snapshot)
    # 摘要里抽一句线索（去掉过长）
    clue = re.sub(r"\s+", " ", snapshot)[:80] if snapshot else ""

    # ---- 高置信专用路由（可扩展，但非唯一路径）----
    special = _special_routes(title, snapshot)
    if special:
        return special

    # ---- 按体裁 + 实体生成（保证每条不同）----
    return _genre_plan(title, snapshot, source, genre, core, core2, num, clue, ents)


def _special_routes(title: str, snapshot: str) -> dict[str, Any] | None:
    """只放高置信实体路由；新热点主要依赖 _genre_plan。"""
    t = title
    text = f"{title} {snapshot}"

    if _has(t, "Opus") and _has(t, "GPT", "评测", "Sol", "定价"):
        return _pack(
            "别跟风：自建评测表",
            "全网在吵新模型定价/智商——先别转发营销图。用「同题评测表」三栏（题型·成本·稳定性）现场跑两道题，自己验收。",
            [
                "镜头1（0-3s）：两模型名称分屏对线截图",
                "镜头2（3-18s）：画出评测三栏模板",
                "镜头3（18-50s）：同题写作实测，黄框差异",
                "镜头4（50-75s）：同题代码/报错实测+计时",
                "镜头5（75-95s）：填表结论：别信单次运气",
                "镜头6（95-end）：空白评测表定格可截图",
            ],
            "75-100秒",
            ["双模型分屏", "角落计时器", "大号评分表"],
        )

    if _has(t, "蒸馏"):
        return _pack(
            "蒸馏争议3分钟讲清",
            "「蒸馏=偷模型」和「蒸馏是常识」同时刷屏——别站队。3 分钟只讲清：合法小模型蒸馏 vs 隐蔽工业级蒸馏差在哪，创作者怎么用开源不翻车。",
            [
                "镜头1（0-3s）：正反标题对撞",
                "镜头2（3-20s）：一句话定义蒸馏",
                "镜头3（20-45s）：合法路径：公开权重/论文/自有数据",
                "镜头4（45-70s）：争议路径：隐蔽大规模 API 抓取（只讲边界）",
                "镜头5（70-90s）：创作者合规：标注来源与协议",
                "镜头6（90-end）：评论区投票题",
            ],
            "60-90秒",
            ["红蓝分栏", "事件时间线", "合规小字"],
        )

    # Codex/Agent 接管 PS / 设计软件 —— 用户明确偏好的小白向
    if _has(t, "Codex", "Cursor", "Claude") and _has(
        t, "Photoshop", "PS", "修图", "P图", "调色", "接管", "剪映", "Figma"
    ):
        tool = "Codex" if _has(t, "Codex") else ("Cursor" if _has(t, "Cursor") else "Claude")
        app = "Photoshop" if _has(t, "Photoshop", "PS", "修图", "P图", "调色") else "设计软件"
        return _pack(
            f"{tool}接管{app[:2]}这样用",
            f"别再把原图丢给 AI 来回传——正确打开方式是让 {tool} 直接操作 {app} 做无损修图/调色。"
            f"我按「连接→下指令→验收」三步，普通人电脑上就能跟。",
            [
                f"镜头1（0-3s）：错误示范「上传图片到对话框」打红叉 + 正确「接管{app}」打绿勾",
                f"镜头2（3-20s）：环境：本机已装 {app}，{tool}/Agent 具备电脑操作权限（打码密钥）",
                f"镜头3（20-50s）：一句人话指令：修图目标（曝光/去瑕疵/调色风格）",
                f"镜头4（50-80s）：录屏看 {tool} 点选菜单/图层，强调「图没离开你电脑」",
                "镜头5（80-100s）：前后对比 + 常见翻车（破解版软件/权限不够）",
                "镜头6（100-end）：复制口令模板卡：你只要改「风格/强度」两个词",
            ],
            "70-100秒",
            ["错误vs正确分屏", f"{app}界面打码个人信息", "前后对比滑杆"],
        )

    if _has(t, "KAT-Coder", "开权") and _has(t, "Coder", "Qwen", "35B", "Apache"):
        return _pack(
            "开源Coder：跟我跑通",
            f"开源 Coder 来了（{title[:24]}…）。不讲虚的：环境→拉取→跑通一次补全，三步跟做。",
            [
                "镜头1（0-3s）：HF/仓库页+许可证",
                "镜头2（3-22s）：显存与环境检查",
                "镜头3（22-50s）：拉取与安装命令黄框",
                "镜头4（50-80s）：真实代码补全/修 bug",
                "镜头5（80-100s）：与闭源 Coder 取舍",
                "镜头6（100-end）：命令清单卡",
            ],
            "90-120秒",
            ["深色终端", "勿露密钥", "成功失败都拍"],
        )

    if _has(t, "MCP") or _has(t, "Topview"):
        return _pack(
            "工作流一条龙怎么砍",
            "旧工作流多标签来回切，新 MCP/一体化工具号称一条龙——拆旧流看砍哪几步，适不适合你的带货/内容岗。",
            [
                "镜头1（0-3s）：多标签 vs 单窗口反差",
                "镜头2（3-18s）：白板画旧流步骤打红叉",
                "镜头3（18-45s）：演示信号/数据接入（打码）",
                "镜头4（45-70s）：选题到素材生成",
                "镜头5（70-90s）：排期/画布成片",
                "镜头6（90-end）：最小三步模板卡",
            ],
            "70-100秒",
            ["数据打码", "前后对比同案例"],
        )

    if _has(t, "Kimi") and _has(t, "90%", "Agent", "工具栈"):
        return _pack(
            "Agent死穴：只活自家栈",
            "九成 AI 产品会死？死因常不是模型弱，是 Agent 只会在自家工具栈装死。三道自检：跨工具、失败回退、无 UI 可跑。",
            [
                "镜头1（0-3s）：「90%失败」大字幕",
                "镜头2（3-15s）：金句拆解",
                "镜头3（15-40s）：自检跨工具",
                "镜头4（40-60s）：自检失败回退",
                "镜头5（60-80s）：自检无 UI",
                "镜头6（80-end）：伪 Agent 反例+清单",
            ],
            "60-90秒",
            ["三勾动效", "金句截图条"],
        )

    if _has(t, "Kimi K3", "KimiK3", "K3") and _has(t, "DeepSeek", "本地", "华为", "霸权", "冲击"):
        return _pack(
            "Kimi K3：本地冲击拆解",
            "外媒把 Kimi K3 说成比 DeepSeek 更大的波——重点不是吓你换模型，是三层变化：成本、能力、可私有化本地下载托管（含国产芯片叙事）。创作者怎么讲才不跟风。",
            [
                "镜头1（0-3s）：字幕「Kimi K3 vs DeepSeek」+ 双冲击图标",
                "镜头2（3-20s）：DeepSeek 当年是成本冲击；K3 被描述为成本+能力",
                "镜头3（20-45s）：「可下载托管」对数据不出域意味着什么（企业/创作者）",
                "镜头4（45-70s）：芯片叙事：华为/国产算力说法如何影响内容角度（标注待核实）",
                "镜头5（70-90s）：拍法：对比表三栏——价格感、是否可本地、适用场景",
                "镜头6（90-end）：行动：先列你的数据是否必须本地，再决定要不要追新模型",
            ],
            "70-100秒",
            ["对比三栏表", "本地/云图标", "待核实水印"],
        )

    if _has(t, "小红书") and _has(t, "起号", "爆款标题"):
        return _pack(
            "小红书AI起号流水线",
            "起号期还在手搓每篇？把主题→初稿→标题 A/B→排期压成流水线，AI 出骨架、人设必须手写。",
            [
                "镜头1（0-3s）：产能×3",
                "镜头2（3-22s）：主题出初稿，圈必须改的个人经验",
                "镜头3（22-45s）：5 标题打分 A/B",
                "镜头4（45-70s）：热点词正确接法",
                "镜头5（70-90s）：7 日排期表",
                "镜头6（90-end）：人设手写区标红",
            ],
            "60-90秒",
            ["演示号", "标题并排"],
        )

    if _has(t, "点点"):
        return _pack(
            "点点AI：能用别全交",
            "点点有人夸有人嫌——关键是：哪些环节能交 AI，哪些一交就「没人味」。",
            [
                "镜头1（0-3s）：入口+争议字幕",
                "镜头2（3-20s）：脑暴可用",
                "镜头3（20-45s）：原文直发翻车对比",
                "镜头4（45-70s）：润色+自补细节",
                "镜头5（70-90s）：隐私/同质化/治理三条雷",
                "镜头6（90-end）：人设段落模板",
            ],
            "70-95秒",
            ["好坏分屏", "小号演示"],
        )

    if _has(t, "照片", "视频发给", "不要随意"):
        return _pack(
            "别乱传：AI隐私三刀",
            "别随意把照片视频丢给 AI：脸、家、证件、孩子进模型往往难撤回。三刀：绝对不传、打码才传、传完自救。",
            [
                "镜头1（0-3s）：热搜+先别传",
                "镜头2（3-18s）：风险地图",
                "镜头3（18-40s）：打码演示",
                "镜头4（40-60s）：本地/只描述替代",
                "镜头5（60-80s）：已传自救",
                "镜头6（80-end）：家庭公约",
            ],
            "60-85秒",
            ["假人像素材", "打码放慢"],
        )

    if _has(t, "GitHub Actions", "自动抓") or _has(text, "xiaohongshu-daily"):
        return _pack(
            "开源：热点自动变笔记",
            "开源方案可每天自动抓热点生成笔记草稿——Fork、Secrets、跑通第一次 Actions，再改成你的垂类。",
            [
                "镜头1（0-3s）：仓库+绿勾",
                "镜头2（3-25s）：Fork 与数据源说明",
                "镜头3（25-55s）：Secrets 打码配置",
                "镜头4（55-80s）：手动 Run 看输出",
                "镜头5（80-100s）：改垂类关键词",
                "镜头6（100-end）：下一步接发布",
            ],
            "90-120秒",
            ["Secrets 马赛克", "深色 GitHub"],
        )

    if _has(t, "Kill Switch", "安全开关"):
        return _pack(
            "AI急停：普通人3开关",
            "监管在谈 Kill Switch，你每天用 Agent——先装三道急停：权限最小化、外网隔离、发布人工终审。",
            [
                "镜头1（0-3s）：新闻+急停不是吓你",
                "镜头2（3-18s）：背景 20 秒",
                "镜头3（18-40s）：权限开关",
                "镜头4（40-60s）：联网开关",
                "镜头5（60-80s）：终审开关",
                "镜头6（80-end）：自动发布默认关",
            ],
            "60-90秒",
            ["三开关图标", "冷静旁白"],
        )

    if _has(t, "零日", "沙盒", "Hugging Face") and _has(t, "跑分", "作弊", "逃逸", "GPT"):
        return _pack(
            "跑分神话？3招自检",
            "跑分/逃逸类争议先别恐慌转发。三招辨真能力：私有题重测、看工具权限日志、同题连跑稳定性。",
            [
                "镜头1（0-3s）：热帖截图+待核实",
                "镜头2（3-20s）：跑分激励如何扭曲行为",
                "镜头3（20-45s）：私有题重测",
                "镜头4（45-65s）：权限/日志",
                "镜头5（65-85s）：连跑 5 次",
                "镜头6（85-end）：业务 3 题表",
            ],
            "75-100秒",
            ["克制表述", "大数字三招"],
        )

    if _has(t, "DeepSeek") and _has(t, "华为") and len(t) < 30:
        return _pack(
            "DeepSeek×华为：看3层",
            "热搜只有两个 Logo 时，你要讲清三层：模型/芯片/行业方案可能落点，以及开发者别抢跑改生产依赖。",
            [
                "镜头1（0-3s）：热搜+双品牌",
                "镜头2（3-20s）：三层架构图",
                "镜头3（20-45s）：内容怎么讲不像软广",
                "镜头4（45-70s）：开发者等待官方说明",
                "镜头5（70-90s）：信息核验",
                "镜头6（90-end）：关注清单",
            ],
            "55-80秒",
            ["分层图", "不传谣"],
        )

    return None


def _genre_plan(
    title: str,
    snapshot: str,
    source: str,
    genre: str,
    core: str,
    core2: str,
    num: str,
    clue: str,
    ents: list[str],
) -> dict[str, Any]:
    """通用内容解析：用实体+体裁保证每条不同。"""
    ent_str = "、".join(ents[:4]) if ents else core
    src_hint = ""
    if "zhihu" in (source or ""):
        src_hint = "知乎热议"
    elif "weibo" in (source or ""):
        src_hint = "微博热搜"
    elif "x:" in (source or "") or "twitter" in (source or ""):
        src_hint = "海外 X 热议"
    elif "rss" in (source or ""):
        src_hint = "科技资讯"
    elif "web:" in (source or ""):
        src_hint = "站外热帖"

    # fingerprint 让同体裁也有差异
    fp = int(hashlib.md5(title.encode()).hexdigest()[:6], 16)
    angle = ["反直觉", "可跟做", "避坑", "对照实验", "一分钟结构"][fp % 5]

    if genre == "tutorial":
        cover = f"{core[:8]}：三步跟做" if len(core) <= 8 else f"跟做：{core[:6]}"
        hook = (
            f"{src_hint + '：' if src_hint else ''}"
            f"别只会收藏「{title[:18]}」——围绕 {core}，我按可复现顺序拆："
            f"准备条件、主操作、验收标准。{('关键数字 ' + num + '。') if num else ''}"
        )
        steps = [
            f"镜头1（0-3s）：先秀「{core}」成功结果/界面，口播 hook 原句",
            f"镜头2（3-18s）：你为什么需要它（痛点，点出 {core2}）",
            f"镜头3（18-45s）：步骤一准备：账号/工具/材料（只列本条相关）",
            f"镜头4（45-75s）：步骤二主操作：演示 {core} 关键点击，黄框标注",
            f"镜头5（75-100s）：步骤三验收：怎样算成功（对照 {ent_str}）",
            f"镜头6（100-end）：本条专属失败点 + 下期预告（{angle}）",
        ]
        dur = "80-120秒"
        visuals = [f"录屏聚焦 {core}", "命令/按钮黄框", "竖屏大字幕"]

    elif genre == "review":
        cover = f"{core[:6]}横评怎么看" if not num else f"{num}看懂对比"
        hook = (
            f"又在吵 {core} 对 {core2}——别站队。用同题对照："
            f"题型、成本、稳定性，{angle}视角 60 秒给你结论框架。"
        )
        steps = [
            f"镜头1（0-3s）：{core} vs {core2} 名称分屏",
            "镜头2（3-18s）：评测维度三栏上屏",
            f"镜头3（18-48s）：同题实测 A（围绕 {core}）",
            f"镜头4（48-75s）：同题实测 B（围绕 {core2}）",
            "镜头5（75-95s）：填表：赢在哪、别信什么",
            "镜头6（95-end）：空白表定格可截图",
        ]
        dur = "70-100秒"
        visuals = ["分屏", "计时器", "评分表"]

    elif genre == "controversy":
        cover = f"{core[:8]}：别急着站队"
        hook = (
            f"{'热搜在吵' if not src_hint else src_hint}「{title[:20]}」。"
            f"我不输出情绪，只给你框架：正方、反方、还缺什么证据。焦点在 {core}。"
        )
        steps = [
            f"镜头1（0-3s）：正反观点各一句，点名 {core}",
            f"镜头2（3-22s）：正方最强论据（结合 {core}）",
            f"镜头3（22-45s）：反方最强论据（结合 {core2}）",
            f"镜头4（45-70s）：信息缺口：现在还不能定论的点",
            f"镜头5（70-90s）：你的可执行立场一句话（{angle}）",
            "镜头6（90-end）：评论区投票",
        ]
        dur = "60-90秒"
        visuals = ["红蓝分栏", "证据清单", "冷静配色"]

    elif genre == "privacy":
        cover = f"隐私：{core[:6]}别乱做"
        hook = (
            f"关于「{title[:18]}」——不是恐吓，是边界。"
            f"围绕 {core}：什么绝对不做、什么打码才做、做完怎么补救。"
        )
        steps = [
            f"镜头1（0-3s）：风险结论字幕（{core}）",
            "镜头2（3-20s）：风险地图：人脸/证件/环境信息",
            "镜头3（20-45s）：正确操作演示（打码/本地）",
            "镜头4（45-65s）：错误示范（打码）",
            "镜头5（65-85s）：已经发生后的补救",
            "镜头6（85-end）：家庭/团队公约一条",
        ]
        dur = "60-85秒"
        visuals = ["打码演示", "清单卡", "假人像"]

    elif genre == "workflow":
        cover = f"{core[:8]}工作流拆解"
        hook = (
            f"别再多开五个标签硬撑——「{title[:16]}」本质是工作流问题。"
            f"我拆：旧流浪费点、新流最小三步、谁适合用 {core}。"
        )
        steps = [
            f"镜头1（0-3s）：旧流混乱 vs 新流一屏（{core}）",
            "镜头2（3-20s）：白板画旧步骤，标冗余",
            f"镜头3（20-50s）：演示关键节点 1（{core}）",
            f"镜头4（50-75s）：演示关键节点 2（{core2}）",
            "镜头5（75-95s）：适合/不适合人群",
            "镜头6（95-end）：最小三步模板",
        ]
        dur = "70-100秒"
        visuals = ["流程箭头", "打码后台", "模板卡"]

    elif genre == "finance":
        cover = f"{num or core[:6]}：财报怎么读" if num else f"{core[:8]}：数字含义"
        hook = (
            f"财经热讯「{title[:18]}」别当段子。"
            f"只抓三行：数字、信号、和你的关系。关键词 {ent_str}。"
        )
        steps = [
            f"镜头1（0-3s）：关键数字上屏 {num or core}",
            "镜头2（3-22s）：数字从哪来、说明什么",
            "镜头3（22-48s）：行业/竞争一层含义",
            "镜头4（48-70s）：对普通人/创作者可感知影响",
            "镜头5（70-90s）：风险与「非投资建议」",
            "镜头6（90-end）：三行复述模板",
        ]
        dur = "55-80秒"
        visuals = ["数字动效", "来源角标", "免责声明"]

    elif genre == "policy":
        cover = f"{core[:8]}：你要守的线"
        hook = (
            f"政策/监管向热点「{title[:16]}」——你不一定立法，但每天在用工具。"
            f"围绕 {core}：背景、对你的约束、今晚能做的三道开关。"
        )
        steps = [
            "镜头1（0-3s）：政策关键词+冷静旁白",
            f"镜头2（3-20s）：20 秒背景（{core}）",
            "镜头3（20-45s）：对个人使用者的约束 1",
            "镜头4（45-65s）：约束 2",
            "镜头5（65-85s）：可执行开关/清单",
            "镜头6（85-end）：不传谣、看官方原文",
        ]
        dur = "60-90秒"
        visuals = ["关键词卡", "清单", "官方来源提示"]

    elif genre == "product":
        cover = f"{core[:8]}：怎么讲清楚"
        hook = (
            f"{src_hint + '·' if src_hint else ''}产品向热点「{title[:18]}」。"
            f"不供神：{core} 解决什么、边界在哪、你能不能现在就试用。"
        )
        steps = [
            f"镜头1（0-3s）：产品/人名标识（{core}）",
            "镜头2（3-20s）：一句话价值",
            f"镜头3（20-50s）：功能/方法拆 2 点（含 {core2}）",
            "镜头4（50-75s）：边界与不适合谁",
            "镜头5（75-95s）：最小试用路径",
            "镜头6（95-end）：行动作业一句",
        ]
        dur = "65-95秒"
        visuals = ["产品界面或图标", "两点卡片", "试用路径"]

    else:  # explain / news_brief
        cover = f"{core[:10]}" if len(core) <= 10 else f"{core[:8]}…"
        if not re.search(r"\d|！|？", cover):
            cover = f"{angle}：{core[:6]}"
        hook = (
            f"{src_hint + '：' if src_hint else ''}"
            f"标题党之外，「{title[:20]}」真正结构是："
            f"{core} 是什么、为什么热、你能做什么。"
            f"{('线索：' + clue[:36] + '…') if clue else ''}"
        )
        steps = [
            f"镜头1（0-3s）：重述冲突点（必须出现 {core}）",
            f"镜头2（3-20s）：谁在推热度/背景（{core2}）",
            f"镜头3（20-50s）：机制或故事线拆解（实体：{ent_str}）",
            f"镜头4（50-75s）：反直觉误判（{angle}）",
            "镜头5（75-95s）：一个可执行小动作",
            "镜头6（95-end）：互动提问（本条专属）",
        ]
        dur = "55-85秒"
        visuals = [f"关键词「{core}」动效", "分层信息卡", "竖屏字幕"]

    # 封面长度
    cover = re.sub(r"\s+", "", cover)
    if len(cover) > 16:
        cover = cover[:14] + "…"

    return _pack(cover, hook, steps, dur, visuals)


def _pack(cover: str, hook: str, steps: list[str], dur: str, visuals: list[str]) -> dict[str, Any]:
    return {
        "爆款封面标题": cover,
        "口播开场钩子": hook,
        "分步骤实操拍摄流程": steps,
        "推荐视频时长": dur,
        "拍摄画面参考": visuals,
    }


def ensure_batch_unique(plans: list[dict[str, Any]], titles: list[str]) -> list[dict[str, Any]]:
    """批次内强制钩子/分镜唯一；冲突则注入标题实体二次改写。"""
    seen_hooks: set[str] = set()
    seen_steps: set[tuple[str, ...]] = set()
    out = []
    for i, (plan, title) in enumerate(zip(plans, titles)):
        p = dict(plan)
        hook = p.get("口播开场钩子") or ""
        steps = list(p.get("分步骤实操拍摄流程") or [])
        ents = extract_entities(title)
        tag = ents[0] if ents else title[:12]

        if hook in seen_hooks or not hook:
            hook = f"专门讲「{title[:22]}」：聚焦 {tag}，60 秒只给你可执行结构，不灌鸡汤。"
            p["口播开场钩子"] = hook
        # 仍冲突
        n = 1
        base_hook = p["口播开场钩子"]
        while p["口播开场钩子"] in seen_hooks:
            p["口播开场钩子"] = f"{base_hook}（角度{n}·{tag}）"
            n += 1
        seen_hooks.add(p["口播开场钩子"])

        st = tuple(steps)
        if st in seen_steps or not steps:
            steps = [
                f"镜头1（0-3s）：本条开场必须出现「{tag}」",
                f"镜头2（3-20s）：背景：{title[:24]}",
                f"镜头3（20-50s）：核心拆解 {tag}",
                f"镜头4（50-75s）：可执行动作（针对本条）",
                f"镜头5（75-end）：收束+互动（唯一提问：你会怎么用{tag}？）",
            ]
            p["分步骤实操拍摄流程"] = steps
            st = tuple(steps)
        n = 1
        while st in seen_steps:
            steps = list(steps)
            steps[0] = f"镜头1（0-3s）：批次去重开场 #{i+1} · {tag}"
            p["分步骤实操拍摄流程"] = steps
            st = tuple(steps)
            n += 1
            if n > 5:
                break
        seen_steps.add(tuple(p["分步骤实操拍摄流程"]))
        out.append(p)
    return out


def validate_unique(packages: list[dict]) -> tuple[bool, str]:
    hooks = [p.get("口播开场钩子") or "" for p in packages]
    steps = [tuple(p.get("分步骤实操拍摄流程") or []) for p in packages]
    if len(hooks) != len(set(hooks)):
        return False, f"钩子不唯一：{len(set(hooks))}/{len(hooks)}"
    if len(steps) != len(set(steps)):
        return False, f"分镜不唯一：{len(set(steps))}/{len(steps)}"
    # 禁止经典套话
    bad = [h for h in hooks if "我花了半小时实测，结论和热搜完全不是一回事" in h]
    if bad:
        return False, f"检测到禁止套话 x{len(bad)}"
    return True, "ok"
