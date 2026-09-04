# -*- coding: utf-8 -*-
"""战略模块：基于企业实际知识产权数据自动生成规避设计战略与风险战略条目。

规则引擎按资产的状态、年费到期日、保护期限、类型结构等维度推导可执行建议，
生成结果写入 strategies 表（source='auto'），用户可在界面上增删改。
"""
import json
import sqlite3
from datetime import datetime, date

from db import connect

TODAY = date(2026, 9, 4)

# 保护期限规则（年），用于推导到期日与布局建议
PROTECT_YEARS = {
    "发明专利": 20,
    "实用新型专利": 10,
    "外观设计专利": 15,
    "软件著作权": 50,
    "作品著作权": 50,
    "注册商标": 10,
    "数据资源登记": 2,
    "数据产品登记": 2,
}
RENEWABLE = {"注册商标", "数据资源登记", "数据产品登记"}

RISK_ORDER = {"高": 0, "中": 1, "低": 2}


def _pdate(s):
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _days(d):
    """距今天的天数，正数表示未来"""
    if d is None:
        return None
    return (d - TODAY).days


def _load_assets(conn):
    rows = conn.execute("SELECT * FROM assets ORDER BY id").fetchall()
    out = []
    for r in rows:
        a = dict(r)
        try:
            a["scope_items"] = json.loads(a.get("scope_items") or "[]")
        except Exception:
            a["scope_items"] = []
        a["_end"] = _pdate(a.get("protect_end"))
        a["_fee"] = _pdate(a.get("next_fee_date"))
        a["_app"] = _pdate(a.get("app_date"))
        a["_grant"] = _pdate(a.get("grant_date"))
        out.append(a)
    return out


def _add(items, seen, **kw):
    key = kw["title"]
    if key in seen:
        return
    seen.add(key)
    kw.setdefault("risk_level", "中")
    kw.setdefault("owner", "知识产权部")
    kw.setdefault("status", "待启动")
    kw.setdefault("source", "auto")
    kw.setdefault("deadline", "")
    kw.setdefault("category", "")
    kw.setdefault("content", "")
    kw.setdefault("actions", "")
    items.append(kw)


# --------------------------------------------------------------------------
# 规避设计战略
# --------------------------------------------------------------------------
def build_avoid(assets, company):
    items, seen = [], set()

    patents = [a for a in assets if a["category"] == "专利"]
    inv = [a for a in patents if a["sub_type"] == "发明专利"]
    um = [a for a in patents if a["sub_type"] == "实用新型专利"]
    des = [a for a in patents if a["sub_type"] == "外观设计专利"]
    sw = [a for a in assets if a["sub_type"] == "软件著作权"]
    tm = [a for a in assets if a["category"] == "商标"]
    data = [a for a in assets if a["category"] == "数据知识产权"]
    valid = [a for a in assets if a["status"] in ("有效", "已授权", "已登记", "已注册", "质押", "许可")]

    # 1. 围绕竞争对手专利的规避设计
    rivals = sorted({a["rival_ref"].strip() for a in assets
                     if a.get("rival_ref") and a["rival_ref"].strip() not in ("", "—", "-")})
    if rivals:
        _add(items, seen, module="avoid", category="规避设计",
             title="围绕主要竞争对手专利族开展规避设计",
             risk_level="中",
             content=("系统登记的资产中标注了如下竞争对手/同类专利族：%s。"
                      "建议以其独立权利要求为基准做逐项技术特征比对，"
                      "识别我方产品方案中落入其保护范围的技术特征，"
                      "并通过替换技术手段、减少技术特征、改变技术路径三种方式实施规避。"
                      % "；".join(rivals[:6])),
             actions=("1. 委托代理机构对上述专利族出具权利要求对照表（Claim Chart）；\n"
                      "2. 对判定为高风险的特征，组织研发出具替代方案并完成规避设计评审；\n"
                      "3. 规避方案定型后立即申请专利，形成自有保护。"),
             owner="研发中心 / 知识产权部",
             deadline=(TODAY.replace(year=TODAY.year, month=12, day=31).isoformat()))

    # 2. 外围专利布局
    core = [a for a in inv if a["status"] in ("有效", "已授权", "质押", "许可")]
    if core and len(um) + len(des) < len(core) * 2:
        _add(items, seen, module="avoid", category="外围专利布局",
             title="核心发明专利的外围包围布局不足",
             risk_level="中",
             content=("现有核心发明专利 %d 件，实用新型与外观设计合计 %d 件，"
                      "外围专利与核心专利数量比约为 %.1f:1，低于推荐的 2:1 至 3:1。"
                      "外围布局偏薄会使竞争对手容易通过规避设计绕开核心专利。"
                      % (len(core), len(um) + len(des), (len(um) + len(des)) / max(len(core), 1))),
             actions=("1. 围绕核心专利的结构实现、参数优选、应用场景三个方向补充实用新型申请；\n"
                      "2. 对产品外观同步申请外观设计，形成\"发明+实用+外观\"三层保护；\n"
                      "3. 优先在核心专利授权后 12 个月内完成外围申请，避免自身公开破坏新颖性。"),
             owner="研发中心")

    # 3. 防御性公开
    rejected = [a for a in assets if a["status"] in ("驳回", "撤回", "失效", "终止")]
    if rejected:
        names = "、".join(a["name"] for a in rejected[:3])
        _add(items, seen, module="avoid", category="防御性公开",
             title="失效/驳回技术的防御性公开与技术秘密转化",
             risk_level="低",
             content=("以下资产已处于驳回或失效状态：%s。对其中技术仍具价值、"
                      "但已因公开而丧失专利授权可能的方案，建议采用防御性公开，"
                      "使其成为现有技术，阻断竞争对手就同一方案获得独占权；"
                      "对其中未公开的技术诀窍，转为技术秘密保护。" % names),
             actions=("1. 逐项评估：可专利性丧失的走防御性公开，未公开的走技术秘密；\n"
                      "2. 防御性公开材料需完整披露技术方案并留存时间戳证据；\n"
                      "3. 技术秘密须签订保密协议并建立接触审批台账。"),
             owner="知识产权部")

    # 4. 挖掘与申报策略
    if assets:
        years = sorted({(a["_app"].year if a["_app"] else TODAY.year) for a in assets})
        recent = [a for a in assets if a["_app"] and (TODAY - a["_app"]).days <= 365]
        rate = len(inv) / max(len(patents), 1)
        _add(items, seen, module="avoid", category="挖掘与申报策略",
             title="研发项目专利挖掘与申报节奏优化",
             risk_level="低",
             content=("近 12 个月提交申请 %d 件，发明专利占专利总量比例为 %.0f%%。"
                      "建议将专利挖掘前移到研发流程，在立项评审嵌入专利检索、"
                      "在样机评审嵌入专利挖掘会，使发明专利占比稳定在 50%% 以上，"
                      "提升专利组合的整体质量与技术壁垒高度。"
                      % (len(recent), rate * 100)),
             actions=("1. 建立\"立项检索—中期挖掘—结题申报\"三节点制度并纳入研发流程文件；\n"
                      "2. 每个在研项目结题前至少产出 1 件发明专利申请；\n"
                      "3. 将专利产出数量与质量纳入研发人员年度绩效考核。"),
             owner="知识产权部 / 研发中心")

    # 5. 技术进入公有领域的机会（专利即将到期）
    soon = [a for a in patents if a["_end"] and 0 < _days(a["_end"]) <= 1095]
    if soon:
        _add(items, seen, module="avoid", category="规避设计",
             title="临近到期专利形成的自由实施机会",
             risk_level="低",
             content=("以下专利将在三年内保护期届满：%s。到期后技术方案进入公有领域，"
                      "可自由实施，建议提前完成技术消化与产品化准备，"
                      "同时核查是否存在同族专利仍在有效期内。"
                      % "、".join(a["name"] for a in soon[:4])),
             actions=("1. 建立到期专利跟踪清单，标注确切到期日与同族情况；\n"
                      "2. 对可自由实施的技术方案做内部技术培训与产品化评估；\n"
                      "3. 在到期日前避免实施，防止侵权风险。"),
             owner="研发中心")

    # 6. 软件+专利组合保护
    if sw and inv:
        _add(items, seen, module="avoid", category="专利布局",
             title="软件类成果的\"专利 + 软著\"组合保护",
             risk_level="低",
             content=("现有软件著作权 %d 件、发明专利 %d 件。软件著作权仅保护代码表达，"
                      "不延及算法与技术方案；对核心算法与业务方法应同步申请发明专利，"
                      "形成\"代码表达 + 技术方案\"的双重保护，"
                      "并注意先申请专利后公开发表论文或产品手册。" % (len(sw), len(inv))),
             actions=("1. 梳理现有软著对应的核心算法，筛选可专利化的技术方案；\n"
                      "2. 严格执行\"先申请、后公开\"流程，论文与手册发布前完成申请；\n"
                      "3. 对不宜公开的算法以技术秘密方式保护。"),
             owner="知识产权部")

    # 7. 标准必要专利
    if any("标准" in (a["name"] or "") or "电力" in (a["tech_field"] or "") for a in assets):
        _add(items, seen, module="avoid", category="标准必要专利",
             title="标准必要专利（SEP）布局与许可策略",
             risk_level="中",
             content=("公司业务涉及电力标准数字化与行业规范衔接，"
                      "若自有技术方案被纳入行业标准或团体标准，即可能形成标准必要专利。"
                      "建议主动参与标准制定，在标准草案形成前完成专利申请，"
                      "并承诺以 FRAND 条件许可，既争取话语权又避免被认定为专利挟持。"),
             actions=("1. 跟踪电力、环保行业标准的制修订计划，识别可纳入自有技术的方向；\n"
                      "2. 参与标准草案讨论前完成相关专利申请；\n"
                      "3. 建立 SEP 清单与 FRAND 许可政策文本。"),
             owner="数字化研究院 / 知识产权部")

    # 8. 海外布局
    overseas = [a for a in assets if a.get("region") and a["region"] != "国内"]
    if not overseas and valid:
        _add(items, seen, module="avoid", category="专利布局",
             title="海外知识产权布局空白",
             risk_level="中",
             content=("现有 %d 件有效/已登记资产的保护地域全部为国内，海外布局为零。"
                      "若产品或技术服务存在出口计划，将面临海外被抢注、"
                      "出口产品落入他人在先专利保护范围的双重风险。" % len(valid)),
             actions=("1. 按目标市场优先级，通过 PCT 或巴黎公约途径提交发明专利申请；\n"
                      "2. 对核心商标办理马德里国际注册或单一国家注册；\n"
                      "3. 出口前完成目标国 FTO 自由实施检索。"),
             owner="知识产权部 / 市场部")

    # 9. 数据知识产权布局
    if data:
        _add(items, seen, module="avoid", category="数据资产布局",
             title="数据知识产权登记与数据资产入表布局",
             risk_level="低",
             content=("现有数据知识产权登记 %d 件。建议按\"数据资源登记—数据产品登记—"
                      "数据资产入表\"的路径推进：先登记原始数据集确立权益，"
                      "再登记加工形成的算法化数据产品，"
                      "最终依据《企业数据资源相关会计处理暂行规定》计入无形资产。"
                      % len(data)),
             actions=("1. 梳理公司全部可登记数据集，按价值与合规成熟度排序分批登记；\n"
                      "2. 数据产品登记须明确算法规则与输出字段，形成可交易的标的；\n"
                      "3. 联合财务部门完成数据资产入表的成本归集与摊销政策。"),
             owner="数字化研究院 / 财务部")

    return items


# --------------------------------------------------------------------------
# 风险战略
# --------------------------------------------------------------------------
def build_risk(assets, company):
    items, seen = [], set()

    # 1. 年费滞纳（最高优先级）
    for a in assets:
        if a["status"] == "年费滞纳":
            d = _days(a["_fee"])
            _add(items, seen, module="risk", category="年费维持风险", risk_level="高",
                 title="年费滞纳：%s 专利权可能终止" % a["name"][:28],
                 content=("%s（%s）当前状态为年费滞纳，应缴日 %s（%s）。"
                          "若在 6 个月滞纳期届满前仍未补缴年费及滞纳金，专利权将自应缴日起终止，"
                          "且该权利已用于量产产品，权利丧失将直接影响产品排他性与质押融资。"
                          % (a["name"], a.get("grant_no") or a.get("app_no") or "—",
                             a.get("next_fee_date") or "—",
                             "已逾期 %d 天" % abs(d) if d is not None and d < 0 else "临近到期")),
                 actions=("1. 立即核定应缴年费与滞纳金（按每月 5% 加收），7 日内完成补缴；\n"
                          "2. 补缴后索取缴费凭证，核对专利登记簿副本的权利状态；\n"
                          "3. 将全部有效专利年费纳入系统台账，设置提前 90 天提醒。"),
                 owner="知识产权部",
                 deadline=(TODAY.replace(day=min(TODAY.day + 30, 28)).isoformat()))

    # 2. 年费到期提醒
    for a in assets:
        d = _days(a["_fee"])
        if d is None or a["status"] == "年费滞纳":
            continue
        if not a.get("next_fee_date"):
            continue
        if d < 0 and a.get("fee_paid") == 0 and a["status"] not in ("失效", "终止", "驳回"):
            _add(items, seen, module="risk", category="年费维持风险", risk_level="高",
                 title="年费逾期未缴：%s" % a["name"][:28],
                 content=("%s 第 %s 年度年费应缴日 %s 已逾期 %d 天且系统未记录缴纳。"
                          % (a["name"], a.get("fee_year") or "—", a["next_fee_date"], abs(d))),
                 actions="1. 核实是否已实际缴纳，若已缴请补录缴费凭证；\n2. 若未缴，评估权利价值后决定补缴或放弃。",
                 owner="知识产权部")
        elif 0 <= d <= 90 and a.get("fee_paid") == 0:
            level = "高" if d <= 30 else ("中" if d <= 60 else "低")
            _add(items, seen, module="risk", category="年费维持风险", risk_level=level,
                 title="年费缴纳提醒：%s（%d 天内）" % (a["name"][:26], d),
                 content=("%s（%s）下一年度年费应缴日为 %s，距今 %d 天，"
                          "年费标准参考 %s。逾期将产生滞纳金，连续逾期将导致权利终止。"
                          % (a["name"], a.get("grant_no") or a.get("app_no") or "—",
                             a["next_fee_date"], d,
                             "发明专利第 1-3 年 900 元、第 4-6 年 1200 元、第 7-9 年 2000 元"
                             if a["sub_type"] == "发明专利" else "实用新型/外观设计第 1-3 年 600 元、第 4-5 年 900 元")),
                 actions=("1. 在应缴日前完成年费缴纳并留存凭证；\n"
                          "2. 同步核查同族专利与关联专利的年费状态；\n"
                          "3. 对于不再维持的非核心专利，及时办理放弃以节约成本。"),
                 owner="知识产权部", deadline=a["next_fee_date"])

    # 3. 商标续展
    for a in assets:
        if a["category"] != "商标" or not a["_end"]:
            continue
        d = _days(a["_end"])
        if d is None:
            continue
        if 0 <= d <= 395:
            level = "高" if d <= 180 else "中"
            _add(items, seen, module="risk", category="商标续展风险", risk_level=level,
                 title="商标续展提醒：%s（%s）" % (a["name"], a["class_no"]),
                 content=("%s 专用权期限至 %s，距今 %d 天。依商标法第四十条，"
                          "续展应在期满前 12 个月内办理，宽展期为期满后 6 个月，"
                          "宽展期内办理需缴纳延迟费；期满未续展将注销商标专用权。"
                          % (a["name"], a["protect_end"], d)),
                 actions=("1. 在期满前 12 个月内提交续展申请并缴纳续展规费；\n"
                          "2. 续展前核查商标样式与实际使用是否一致；\n"
                          "3. 归档近三年商标使用证据（合同、发票、宣传物料）。"),
                 owner="市场部", deadline=a["protect_end"])
        elif d < 0:
            _add(items, seen, module="risk", category="商标续展风险", risk_level="高",
                 title="商标专用权已届满：%s" % a["name"],
                 content=("%s 专用权期限已于 %s 届满，需立即核实是否已办理续展。"
                          % (a["name"], a["protect_end"])),
                 actions="1. 核实续展办理情况；\n2. 若未续展，评估重新申请的可行性并防范他人抢注。",
                 owner="市场部")

    # 3b. 商标续展总览（无论距离远近，均纳入年度管理台账）
    tm_valid = [a for a in assets if a["category"] == "商标" and a["_end"] and _days(a["_end"]) > 395]
    if tm_valid:
        tm_valid.sort(key=lambda a: a["_end"])
        lines = "\n".join("· %s（%s）：专用权至 %s，续展窗口 %s 起" % (
            a["name"], a["class_no"], a["protect_end"],
            a["_end"].replace(year=a["_end"].year - 1).isoformat()) for a in tm_valid[:8])
        _add(items, seen, module="risk", category="商标续展风险", risk_level="低",
             title="商标续展年度管理台账（%d 件）" % len(tm_valid),
             content=("公司现有注册商标 %d 件，专用权期限均为 10 年，"
                      "续展应在期满前 12 个月内办理，宽展期为期满后 6 个月（需缴纳延迟费）。"
                      "建议纳入年度管理台账，在续展窗口开启时自动触发办理。\n%s"
                      % (len(tm_valid), lines)),
             actions=("1. 在每件商标期满前 13 个月启动续展准备，核查使用证据与样式一致性；\n"
                      "2. 续展与商标使用证据归档同步进行，防范续展后被提撤三；\n"
                      "3. 对不再使用的防御商标评估是否放弃，节约续展成本。"),
             owner="市场部")

    # 4. 商标撤三风险
    for a in assets:
        if a["category"] != "商标":
            continue
        # 撤三仅针对已核准注册的商标，未核准的不适用连续三年不使用撤销条款
        if a["status"] in ("申请中", "审查中", "驳回", "失效", "终止"):
            continue
        g = a["_grant"]
        if not g:
            continue
        age = (TODAY - g).days // 365
        if age >= 3:
            _add(items, seen, module="risk", category="商标撤三风险", risk_level="中",
                 title="撤三风险：%s 注册满 %d 年" % (a["name"], age),
                 content=("%s（%s，注册日 %s）核准注册已满 %d 年。"
                          "依商标法第四十九条，注册商标连续三年无正当理由不使用，"
                          "任何单位或个人可申请撤销。若核定使用项目中存在未实际开展的服务，"
                          "须尽快补充使用证据或主动删减。" % (a["name"], a["class_no"],
                                                    a.get("grant_date") or a.get("app_date"), age)),
                 actions=("1. 逐项梳理核定商品/服务的实际使用情况，形成使用证据清单；\n"
                          "2. 对确无使用计划的项目主动提交删减申请，降低被撤范围；\n"
                          "3. 建立商标使用证据年度归档制度（合同、发票、广告、展会材料）。"),
                 owner="市场部 / 知识产权部")

    # 5. 数据知识产权续展 / 合规
    for a in assets:
        if a["category"] != "数据知识产权" or not a["_end"]:
            continue
        d = _days(a["_end"])
        if d is None:
            continue
        if d < 0:
            _add(items, seen, module="risk", category="数据合规风险", risk_level="高",
                 title="数据知识产权登记已失效：%s" % a["name"][:26],
                 content=("%s（%s）登记有效期已于 %s 届满，逾期 %d 天。"
                          "登记证书失效后，在侵权纠纷中难以依据登记证书主张数据权益，"
                          "并将影响数据资产入表的权属证明效力。"
                          % (a["name"], a.get("grant_no") or a.get("app_no") or "—",
                             a["protect_end"], abs(d))),
                 actions=("1. 评估重新登记或补充登记的可行性，尽快重新提交；\n"
                          "2. 同步更新样例数据与数据范围说明；\n"
                          "3. 建立数据知识产权有效期台账，设置到期前 60 天提醒。"),
                 owner="数字化研究院", deadline=a["protect_end"])
        elif d <= 90:
            level = "高" if d <= 30 else "中"
            _add(items, seen, module="risk", category="数据合规风险", risk_level=level,
                 title="数据知识产权续展提醒：%s（%d 天内）" % (a["name"][:24], d),
                 content=("%s（%s）登记有效期至 %s，距今 %d 天。"
                          "数据知识产权登记证书有效期为 2 年，期满需办理续展，"
                          "逾期未续展将丧失登记效力。" % (a["name"],
                                                  a.get("grant_no") or a.get("app_no") or "—",
                                                  a["protect_end"], d)),
                 actions=("1. 在到期前 30 日内提交续展申请并更新样例数据；\n"
                          "2. 同步核查数据来源授权链与脱敏记录的完整性；\n"
                          "3. 将数据知识产权有效期纳入年度提醒台账。"),
                 owner="数字化研究院", deadline=a["protect_end"])

    # 6. 数据合规：授权链与脱敏
    data_assets = [a for a in assets if a["category"] == "数据知识产权"]
    if data_assets:
        _add(items, seen, module="risk", category="数据合规风险", risk_level="中",
             title="数据来源授权链与脱敏合规审查",
             content=("公司现有 %d 件数据知识产权登记，数据来源涵盖自有系统采集与客户现场回传。"
                      "若授权链条不完整（缺少客户数据使用授权、缺少脱敏处理留痕），"
                      "将违反数据安全法、个人信息保护法相关规定，"
                      "并可能导致登记证书被撤销、数据资产入表被审计否决。" % len(data_assets)),
             actions=("1. 全面梳理采集、回传、加工、对外提供各环节的授权文件并补齐缺失项；\n"
                      "2. 建立数据分类分级清单与脱敏操作留痕机制；\n"
                      "3. 对外提供数据产品前完成数据出境与共享的合规审查。"),
             owner="法务 / 数字化研究院")

    # 7. 审查周期过长（发明专利"申请中"属正常待提实审状态，由提实审规则单独覆盖）
    for a in assets:
        if a["status"] in ("审查中", "申请中") and a["_app"]:
            if a["sub_type"] == "发明专利" and a["status"] == "申请中":
                continue
            months = (TODAY - a["_app"]).days // 30
            limit = 30 if a["sub_type"] == "发明专利" else 12
            if months >= limit:
                _add(items, seen, module="risk", category="审查周期风险", risk_level="中",
                     title="审查周期异常：%s 已 %d 个月" % (a["name"][:26], months),
                     content=("%s（申请号 %s，申请日 %s）自申请至今已 %d 个月仍处%s状态，"
                              "超出常规审查周期。需核查是否存在逾期未答复、"
                              "未缴实审费或未办理登记手续等程序性瑕疵。"
                              % (a["name"], a.get("app_no") or "—", a.get("app_date"), months, a["status"])),
                     actions=("1. 登录专利业务办理系统核查通知书答复期限与缴费状态；\n"
                              "2. 对发明专利确认是否已按时提出实质审查请求；\n"
                              "3. 与代理机构确认案件进度并保留沟通记录。"),
                     owner="知识产权部")

    # 8. 发明专利提实审期限
    for a in assets:
        if a["sub_type"] == "发明专利" and a["status"] == "申请中" and a["_app"]:
            months = (TODAY - a["_app"]).days // 30
            if 0 <= months <= 30 and months >= 24:
                left = 36 - months
                _add(items, seen, module="risk", category="审查周期风险", risk_level="高",
                     title="提实审期限临近：%s 剩余约 %d 个月" % (a["name"][:24], left),
                     content=("%s 申请日 %s，依专利法第三十五条，"
                              "实质审查请求应自申请日起 3 年内提出，逾期视为撤回。"
                              % (a["name"], a["app_date"])),
                     actions=("1. 在技术路线确定后立即提出实质审查请求；\n"
                              "2. 同步提出提前公开请求以加快审查；\n"
                              "3. 若暂不拟继续，及时办理主动撤回以节约成本。"),
                     owner="知识产权部")

    # 9. FTO 自由实施
    valid_core = [a for a in assets if a["category"] == "专利"
                  and a["status"] in ("有效", "已授权", "质押", "许可")]
    if valid_core:
        _add(items, seen, module="risk", category="侵权风险（FTO）", risk_level="中",
             title="主营产品 FTO 自由实施检索与侵权预警",
             content=("公司现有有效/已授权专利 %d 件，对应量产产品线。"
                      "专利授权不代表可自由实施，仍需对产品涉及的第三方有效专利做 FTO 检索。"
                      "尤其在产品出口、参展与招投标场景下，"
                      "未做 FTO 将面临被诉侵权、产品下架与招投标资格丧失的风险。" % len(valid_core)),
             actions=("1. 按产品线开展 FTO 检索，输出风险专利清单与权利要求对照表；\n"
                      "2. 对高风险专利采取规避设计、无效宣告或许可谈判；\n"
                      "3. 建立产品上市前的知识产权审查放行制度。"),
             owner="知识产权部 / 法务")

    # 10. 诉讼风险与权利稳定性
    pledged = [a for a in assets if a["status"] == "质押"]
    licensed = [a for a in assets if a["status"] == "许可"]
    if pledged or licensed:
        _add(items, seen, module="risk", category="诉讼风险", risk_level="中",
             title="已质押/许可专利的权利稳定性维护",
             content=("现有质押专利 %d 件、许可专利 %d 件。质押与许可状态下，"
                      "若权利因年费逾期、被宣告无效而失稳，"
                      "将直接触发银行授信风险条款与许可合同违约责任。"
                      % (len(pledged), len(licensed))),
             actions=("1. 对质押专利优先保障年费缴纳，纳入最高优先级台账；\n"
                      "2. 保存研发原始记录与实验数据，应对可能的无效宣告请求；\n"
                      "3. 定期核查被许可方的履约与付费情况。"),
             owner="知识产权部 / 财务部")

    # 11. 失效权利的重建
    dead = [a for a in assets if a["status"] in ("失效", "终止", "驳回", "撤回")]
    if dead:
        _add(items, seen, module="risk", category="权利流失风险", risk_level="中",
             title="失效与驳回资产的复盘与权利重建",
             content=("现有 %d 件资产处于失效/驳回/撤回状态：%s。"
                      "需区分是主动放弃（技术迭代）还是被动丧失（程序失误）。"
                      "若为程序失误导致的权利丧失，应复盘流程并完善提醒机制；"
                      "若技术方案仍有价值，可考虑以新的申请重新布局。"
                      % (len(dead), "、".join(a["name"][:16] for a in dead[:3]))),
             actions=("1. 逐件复盘失效原因，形成原因分类台账；\n"
                      "2. 对程序失误类失效，完善年费与期限的双重提醒机制；\n"
                      "3. 对技术仍具价值的方案，评估重新申请的可行性。"),
             owner="知识产权部")

    # 12. 结构性问题：发明专利占比
    patents = [a for a in assets if a["category"] == "专利"]
    if patents:
        inv_n = len([a for a in patents if a["sub_type"] == "发明专利"])
        ratio = inv_n / len(patents)
        if ratio < 0.4:
            _add(items, seen, module="risk", category="布局结构风险", risk_level="中",
                 title="专利组合质量结构偏低（发明专利占比 %.0f%%）" % (ratio * 100),
                 content=("专利总量 %d 件中发明专利 %d 件，占比 %.0f%%，低于高新技术企业认定"
                          "与专精特新评价中通常认可的合理水平（50%% 以上）。"
                          "实用新型与外观设计占比偏高，虽授权快、成本低，"
                          "但权利稳定性与技术壁垒相对较弱。"
                          % (len(patents), inv_n, ratio * 100)),
                 actions=("1. 提升研发项目的发明专利申报比例，设定年度目标；\n"
                          "2. 对核心技术同步提交发明与实用新型申请（一案两报）；\n"
                          "3. 在高新技术企业复核前完成发明专利数量补强。"),
                 owner="知识产权部")

    # 13. 商标类别覆盖
    tm = [a for a in assets if a["category"] == "商标"]
    if tm:
        cls = set()
        for a in tm:
            for ch in (a.get("class_no") or "").replace("第", " ").split():
                if ch.isdigit():
                    cls.add(int(ch))
        need = {9, 42, 7, 35, 37, 40}
        miss = sorted(need - cls)
        if miss:
            _add(items, seen, module="risk", category="商标布局风险", risk_level="中",
                 title="商标类别覆盖存在缺口（缺第 %s 类）" % "、".join(str(c) for c in miss),
                 content=("现有商标覆盖类别：第 %s 类。对于智能装备与工业软件企业，"
                          "建议至少覆盖第 7 类（机械设备）、第 9 类（软件与仪器）、"
                          "第 37 类（安装维修）、第 40 类（材料处理）、第 42 类（技术服务）。"
                          "缺口类别存在被他人在先注册、进而阻碍公司业务拓展的风险。"
                          % "、".join(str(c) for c in sorted(cls))),
                 actions=("1. 对缺口类别补充注册申请，优先第 37 类；\n"
                          "2. 对主商标办理防御性储备注册，覆盖关联类似群；\n"
                          "3. 建立商标监测，对近似商标及时提异议。"),
                 owner="市场部")

    return items


def generate(conn=None):
    """基于当前数据生成战略条目列表（不落库）"""
    own = conn is None
    if own:
        conn = connect()
    try:
        company = conn.execute("SELECT * FROM company WHERE id=1").fetchone()
        company = dict(company) if company else {}
        assets = _load_assets(conn)
        items = build_avoid(assets, company) + build_risk(assets, company)
        items.sort(key=lambda x: (RISK_ORDER.get(x.get("risk_level"), 3),
                                  0 if x["module"] == "risk" else 1, -len(x["title"])))
        return items
    finally:
        if own:
            conn.close()


def rebuild(conn=None):
    """重新生成自动战略条目，覆盖旧的 auto 条目，保留用户手动条目"""
    own = conn is None
    if own:
        conn = connect()
    try:
        items = generate(conn)
        conn.execute("DELETE FROM strategies WHERE source='auto'")
        now = TODAY.isoformat()
        for it in items:
            d = dict(it)
            d["created_at"] = now
            d["updated_at"] = now
            cols = ",".join(d.keys())
            ph = ",".join("?" * len(d))
            conn.execute(f"INSERT INTO strategies ({cols}) VALUES ({ph})", list(d.values()))
        conn.commit()
        return len(items)
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    n = rebuild()
    print("auto strategies rebuilt:", n)
