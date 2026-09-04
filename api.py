# -*- coding: utf-8 -*-
"""企业知识产权管理系统 - 业务接口层"""
import io
import csv
import json
import sqlite3
import re
from collections import OrderedDict, Counter
from datetime import date, datetime, timedelta

from db import connect
import strategy as strategy_mod

TODAY = date(2026, 9, 4)

CATEGORIES = OrderedDict([
    ("专利", ["发明专利", "实用新型专利", "外观设计专利"]),
    ("著作权", ["软件著作权", "作品著作权"]),
    ("数据知识产权", ["数据资源登记", "数据产品登记"]),
    ("商标", ["注册商标"]),
])
STATUSES = ["申请中", "审查中", "已授权", "已登记", "已注册", "有效", "维持中", "质押", "许可",
            "诉讼中", "年费滞纳", "撤三风险", "驳回", "撤回", "失效", "终止"]
DEPARTMENTS = ["研发中心", "水务事业部", "数字化研究院", "市场部", "知识产权部", "财务部", "法务"]
REGIONS = ["国内", "涉外", "全球"]
LEVELS = ["高", "中", "低"]
MODULE_NAMES = {"avoid": "规避设计战略", "risk": "风险战略"}

# 状态归一化分组
VALID_STATUS = {"有效", "已授权", "已登记", "已注册", "维持中", "质押", "许可", "诉讼中", "撤三风险"}
PENDING_STATUS = {"申请中", "审查中"}
DEAD_STATUS = {"失效", "终止", "驳回", "撤回", "年费滞纳"}


def _d(s):
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _days(s):
    d = _d(s)
    return None if d is None else (d - TODAY).days


def _row2dict(r):
    d = dict(r)
    if "scope_items" in d:
        try:
            d["scope_items"] = json.loads(d["scope_items"] or "[]")
        except Exception:
            d["scope_items"] = []
    return d


def ok(data=None, **kw):
    res = {"ok": True}
    if data is not None:
        res["data"] = data
    res.update(kw)
    return res


def err(msg, code=400):
    return {"ok": False, "error": msg, "code": code}


# --------------------------------------------------------------------------
# 企业信息
# --------------------------------------------------------------------------
def get_company(conn):
    r = conn.execute("SELECT * FROM company WHERE id=1").fetchone()
    return ok(dict(r) if r else {})


def update_company(conn, body):
    fields = ["name", "credit_code", "industry", "company_type", "address", "founded_date",
              "capital", "legal_person", "contact", "phone", "email", "website",
              "ip_dept", "ip_manager", "intro"]
    sets, vals = [], []
    for f in fields:
        if f in body:
            v = body[f]
            if f == "capital":
                try:
                    v = float(v or 0)
                except Exception:
                    v = 0.0
            sets.append(f"{f}=?")
            vals.append(v)
    sets.append("updated_at=?")
    vals.append(TODAY.isoformat())
    vals.append(1)
    conn.execute(f"UPDATE company SET {','.join(sets)} WHERE id=?", vals)
    conn.commit()
    return get_company(conn)


# --------------------------------------------------------------------------
# 知识产权资产
# --------------------------------------------------------------------------
LIST_FIELDS = ("id,category,sub_type,name,app_no,app_date,grant_no,grant_date,applicant,"
               "creators,class_no,tech_field,department,status,status_date,fee_year,fee_paid,"
               "next_fee_date,protect_start,protect_end,region,agency,created_at,updated_at")


def list_assets(conn, q):
    where, args = [], []
    cat = q.get("category", "").strip()
    sub = q.get("sub_type", "").strip()
    st = q.get("status", "").strip()
    dept = q.get("department", "").strip()
    region = q.get("region", "").strip()
    kw = q.get("keyword", "").strip()
    if cat:
        where.append("category=?"); args.append(cat)
    if sub:
        where.append("sub_type=?"); args.append(sub)
    if st:
        where.append("status=?"); args.append(st)
    if dept:
        where.append("department=?"); args.append(dept)
    if region:
        where.append("region=?"); args.append(region)
    if kw:
        like = f"%{kw}%"
        where.append("(name LIKE ? OR app_no LIKE ? OR grant_no LIKE ? OR applicant LIKE ? "
                     "OR creators LIKE ? OR class_no LIKE ? OR tech_field LIKE ? "
                     "OR agency LIKE ? OR remark LIKE ?)")
        args += [like] * 9
    sql = f"SELECT {LIST_FIELDS} FROM assets"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sort = q.get("sort", "updated_at")
    order = "DESC" if q.get("order", "desc").lower() == "desc" else "ASC"
    sort_map = {"updated_at": "updated_at", "app_date": "app_date", "protect_end": "protect_end",
                "next_fee_date": "next_fee_date", "name": "name", "id": "id"}
    sql += " ORDER BY " + sort_map.get(sort, "updated_at") + " " + order
    try:
        page = max(int(q.get("page", 1)), 1)
        size = min(max(int(q.get("page_size", 200)), 1), 2000)
    except Exception:
        page, size = 1, 200
    total_sql = "SELECT COUNT(*) c FROM assets" + (" WHERE " + " AND ".join(where) if where else "")
    total = conn.execute(total_sql, args).fetchone()["c"]
    sql += " LIMIT ? OFFSET ?"
    args += [size, (page - 1) * size]
    rows = [_row2dict(r) for r in conn.execute(sql, args).fetchall()]
    for r in rows:
        r["days_to_fee"] = _days(r.get("next_fee_date"))
        r["days_to_end"] = _days(r.get("protect_end"))
    return ok({"items": rows, "total": total, "page": page, "page_size": size})


ASSET_FIELDS = ["category", "sub_type", "name", "app_no", "app_date", "grant_no", "grant_date",
                "applicant", "creators", "agency", "class_no", "tech_field", "department",
                "status", "status_date", "fee_year", "fee_paid", "next_fee_date",
                "protect_start", "protect_end", "scope_text", "region", "key_points",
                "rival_ref", "remark"]


def _norm_asset_body(body):
    out = {}
    for f in ASSET_FIELDS:
        out[f] = body.get(f, "")
    try:
        out["fee_year"] = int(out["fee_year"] or 0)
    except Exception:
        out["fee_year"] = 0
    out["fee_paid"] = 1 if out.get("fee_paid") in (1, "1", True, "true", "on") else 0
    items = body.get("scope_items")
    if isinstance(items, list):
        out["scope_items"] = json.dumps([str(x) for x in items if str(x).strip()],
                                        ensure_ascii=False)
    elif isinstance(items, str):
        try:
            parsed = json.loads(items)
            out["scope_items"] = json.dumps(parsed, ensure_ascii=False)
        except Exception:
            out["scope_items"] = json.dumps([s for s in re.split(r"[\n;；]", items) if s.strip()],
                                            ensure_ascii=False)
    else:
        out["scope_items"] = json.dumps(out.get("scope_items") or [], ensure_ascii=False)
    return out


def get_asset(conn, aid):
    r = conn.execute("SELECT * FROM assets WHERE id=?", (aid,)).fetchone()
    if not r:
        return err("资产不存在", 404)
    a = _row2dict(r)
    a["days_to_fee"] = _days(a.get("next_fee_date"))
    a["days_to_end"] = _days(a.get("protect_end"))
    logs = conn.execute("SELECT * FROM status_logs WHERE asset_id=? ORDER BY change_date DESC, id DESC",
                        (aid,)).fetchall()
    fees = conn.execute("SELECT * FROM fee_records WHERE asset_id=? ORDER BY year DESC, id DESC",
                        (aid,)).fetchall()
    a["logs"] = [dict(x) for x in logs]
    a["fees"] = [dict(x) for x in fees]
    return ok(a)


def create_asset(conn, body):
    if not (body.get("name") or "").strip():
        return err("知识产权名称不能为空")
    data = _norm_asset_body(body)
    if data["category"] not in CATEGORIES:
        return err("知识产权类型不合法")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["created_at"] = now
    data["updated_at"] = now
    cols = ",".join(data.keys())
    ph = ",".join("?" * len(data))
    cur = conn.execute(f"INSERT INTO assets ({cols}) VALUES ({ph})", list(data.values()))
    conn.commit()
    aid = cur.lastrowid
    # 自动写入首条状态变更记录
    if data["status"]:
        conn.execute("INSERT INTO status_logs(asset_id,change_date,old_status,new_status,note,created_at)"
                     " VALUES (?,?,?,?,?,?)",
                     (aid, data.get("status_date") or data.get("app_date") or TODAY.isoformat(),
                      "", data["status"], "建档登记", now))
        conn.commit()
    return get_asset(conn, aid)


def update_asset(conn, aid, body):
    old = conn.execute("SELECT * FROM assets WHERE id=?", (aid,)).fetchone()
    if not old:
        return err("资产不存在", 404)
    old = _row2dict(old)
    new_status = body.get("status", old.get("status"))
    cur = conn.execute("SELECT status FROM assets WHERE id=?", (aid,)).fetchone()
    data = _norm_asset_body({**old, **{k: v for k, v in body.items() if k in ASSET_FIELDS or k == "scope_items"}})
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sets = ",".join(f"{k}=?" for k in data.keys())
    conn.execute(f"UPDATE assets SET {sets} WHERE id=?", list(data.values()) + [aid])
    # 状态发生变化时自动追加变更记录
    if cur and cur["status"] != new_status:
        conn.execute("INSERT INTO status_logs(asset_id,change_date,old_status,new_status,note,created_at)"
                     " VALUES (?,?,?,?,?,?)",
                     (aid, body.get("status_date") or TODAY.isoformat(), cur["status"],
                      new_status, body.get("log_note") or "状态更新", data["updated_at"]))
    conn.commit()
    return get_asset(conn, aid)


def delete_asset(conn, aid):
    r = conn.execute("SELECT id,name FROM assets WHERE id=?", (aid,)).fetchone()
    if not r:
        return err("资产不存在", 404)
    conn.execute("DELETE FROM assets WHERE id=?", (aid,))
    conn.commit()
    return ok({"id": aid, "name": r["name"]})


# --------------------------------------------------------------------------
# 状态变更记录 / 年费记录
# --------------------------------------------------------------------------
def add_log(conn, aid, body):
    if not conn.execute("SELECT id FROM assets WHERE id=?", (aid,)).fetchone():
        return err("资产不存在", 404)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("SELECT status FROM assets WHERE id=?", (aid,)).fetchone()
    new_status = body.get("new_status") or cur["status"]
    conn.execute("INSERT INTO status_logs(asset_id,change_date,old_status,new_status,note,created_at)"
                 " VALUES (?,?,?,?,?,?)",
                 (aid, body.get("change_date") or TODAY.isoformat(),
                  body.get("old_status") or cur["status"], new_status,
                  body.get("note", ""), now))
    if new_status != cur["status"]:
        conn.execute("UPDATE assets SET status=?, status_date=?, updated_at=? WHERE id=?",
                     (new_status, body.get("change_date") or TODAY.isoformat(), now, aid))
    conn.commit()
    return get_asset(conn, aid)


def delete_log(conn, log_id):
    r = conn.execute("SELECT asset_id FROM status_logs WHERE id=?", (log_id,)).fetchone()
    if not r:
        return err("记录不存在", 404)
    conn.execute("DELETE FROM status_logs WHERE id=?", (log_id,))
    conn.commit()
    return ok({"id": log_id})


def add_fee(conn, aid, body):
    if not conn.execute("SELECT id FROM assets WHERE id=?", (aid,)).fetchone():
        return err("资产不存在", 404)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    paid = 1 if body.get("paid") in (1, "1", True, "true", "on") else 0
    try:
        year = int(body.get("year") or 0)
    except Exception:
        year = 0
    try:
        amount = float(body.get("amount") or 0)
    except Exception:
        amount = 0.0
    conn.execute("INSERT INTO fee_records(asset_id,year,amount,due_date,paid_date,paid,note,created_at)"
                 " VALUES (?,?,?,?,?,?,?,?)",
                 (aid, year, amount, body.get("due_date", ""),
                  body.get("paid_date", "") if paid else "", paid, body.get("note", ""), now))
    # 同步资产主表的年费字段
    if body.get("due_date"):
        conn.execute("UPDATE assets SET fee_year=?, fee_paid=?, next_fee_date=?, updated_at=? WHERE id=?",
                     (year, paid, body["due_date"], now, aid))
    conn.commit()
    return get_asset(conn, aid)


def update_fee(conn, fee_id, body):
    r = conn.execute("SELECT * FROM fee_records WHERE id=?", (fee_id,)).fetchone()
    if not r:
        return err("记录不存在", 404)
    r = dict(r)
    paid = 1 if body.get("paid", r["paid"]) in (1, "1", True, "true", "on") else 0
    conn.execute("UPDATE fee_records SET year=?,amount=?,due_date=?,paid_date=?,paid=?,note=? WHERE id=?",
                 (int(body.get("year", r["year"]) or 0), float(body.get("amount", r["amount"]) or 0),
                  body.get("due_date", r["due_date"]),
                  body.get("paid_date", r["paid_date"]) if paid else "",
                  paid, body.get("note", r["note"]), fee_id))
    conn.commit()
    return get_asset(conn, r["asset_id"])


def delete_fee(conn, fee_id):
    r = conn.execute("SELECT asset_id FROM fee_records WHERE id=?", (fee_id,)).fetchone()
    if not r:
        return err("记录不存在", 404)
    conn.execute("DELETE FROM fee_records WHERE id=?", (fee_id,))
    conn.commit()
    return ok({"id": fee_id})


# --------------------------------------------------------------------------
# 统计与分析
# --------------------------------------------------------------------------
def _all_assets(conn):
    return [_row2dict(r) for r in conn.execute("SELECT * FROM assets").fetchall()]


def stats_overview(conn, q=None):
    rows = _all_assets(conn)
    total = len(rows)
    by_cat, by_status, by_sub, by_dept, by_region = {}, {}, {}, {}, {}
    for a in rows:
        by_cat[a["category"]] = by_cat.get(a["category"], 0) + 1
        s = a["status"] or "未填写"
        by_status[s] = by_status.get(s, 0) + 1
        key = a["sub_type"] or "未分类"
        by_sub[key] = by_sub.get(key, 0) + 1
        d = a["department"] or "未分配"
        by_dept[d] = by_dept.get(d, 0) + 1
        rg = a["region"] or "国内"
        by_region[rg] = by_region.get(rg, 0) + 1

    valid = sum(1 for a in rows if a["status"] in VALID_STATUS)
    pending = sum(1 for a in rows if a["status"] in PENDING_STATUS)
    dead = sum(1 for a in rows if a["status"] in DEAD_STATUS)
    # 风险项：年费滞纳 / 撤三风险 / 已失效登记 / 90 天内到期未缴
    risk = 0
    for a in rows:
        d = _days(a.get("next_fee_date"))
        if a["status"] in ("年费滞纳", "撤三风险", "诉讼中"):
            risk += 1
        elif a["status"] not in DEAD_STATUS and a.get("fee_paid") == 0 and d is not None and d < 90:
            risk += 1
        elif a["status"] not in DEAD_STATUS and a.get("protect_end") and _days(a["protect_end"]) is not None \
                and 0 <= _days(a["protect_end"]) <= 90:
            risk += 1
    expiring = 0
    for a in rows:
        if a["status"] in DEAD_STATUS:
            continue
        d = _days(a.get("protect_end"))
        if d is not None and -1 <= d <= 365:
            expiring += 1

    cat_order = list(CATEGORIES.keys())
    return ok({
        "total": total, "valid": valid, "pending": pending, "dead": dead,
        "risk": risk, "expiring": expiring,
        "valid_rate": round(valid / total * 100, 1) if total else 0,
        "by_category": [{"name": k, "value": by_cat.get(k, 0)} for k in cat_order if by_cat.get(k, 0)],
        "by_status": sorted([{"name": k, "value": v} for k, v in by_status.items()],
                            key=lambda x: -x["value"]),
        "by_sub_type": sorted([{"name": k, "value": v} for k, v in by_sub.items()],
                              key=lambda x: -x["value"]),
        "by_department": sorted([{"name": k, "value": v} for k, v in by_dept.items()],
                                key=lambda x: -x["value"]),
        "by_region": sorted([{"name": k, "value": v} for k, v in by_region.items()],
                            key=lambda x: -x["value"]),
        "status_group": [
            {"name": "有效/已授权", "value": valid},
            {"name": "审查中/申请中", "value": pending},
            {"name": "失效/驳回/滞纳", "value": dead},
        ],
    })


def stats_trend(conn, q=None):
    rows = _all_assets(conn)
    years = {}
    for a in rows:
        y = (a.get("app_date") or "")[:4]
        if y.isdigit():
            years.setdefault(int(y), {"apply": 0, "grant": 0})
            years[int(y)]["apply"] += 1
        g = (a.get("grant_date") or "")[:4]
        if g.isdigit():
            years.setdefault(int(g), {"apply": 0, "grant": 0})
            years[int(g)]["grant"] += 1
    if not years:
        return ok({"years": [], "apply": [], "grant": [], "by_category": {}})
    ys = sorted(years.keys())
    # 补齐中间年份
    ys = list(range(min(ys), max(ys) + 1))
    apply_s = [years.get(y, {}).get("apply", 0) for y in ys]
    grant_s = [years.get(y, {}).get("grant", 0) for y in ys]
    by_cat = {}
    for cat in CATEGORIES:
        cnt = {}
        for a in rows:
            if a["category"] != cat:
                continue
            y = (a.get("app_date") or "")[:4]
            if y.isdigit():
                cnt[int(y)] = cnt.get(int(y), 0) + 1
        by_cat[cat] = [cnt.get(y, 0) for y in ys]
    return ok({"years": [str(y) for y in ys], "apply": apply_s, "grant": grant_s,
               "by_category": by_cat})


def stats_expiry(conn, q=None):
    days = 365
    if q:
        try:
            days = int(q.get("days", 365))
        except Exception:
            days = 365
    rows = _all_assets(conn)
    fee_due, tm_renew, data_renew, patent_expire, overdue = [], [], [], [], []
    for a in rows:
        if a["status"] in ("失效", "终止", "驳回", "撤回"):
            continue
        base = {"id": a["id"], "name": a["name"], "category": a["category"],
                "sub_type": a["sub_type"], "no": a.get("grant_no") or a.get("app_no") or "",
                "department": a["department"], "status": a["status"]}
        d = _days(a.get("next_fee_date"))
        if a.get("next_fee_date") and d is not None:
            item = dict(base, **{"date": a["next_fee_date"], "days": d,
                                 "year": a.get("fee_year"), "paid": a.get("fee_paid")})
            if d < 0 and a.get("fee_paid") == 0 and a["status"] not in DEAD_STATUS:
                overdue.append(item)
            elif -1 <= d <= days and a.get("fee_paid") == 0:
                fee_due.append(item)
        de = _days(a.get("protect_end"))
        if a.get("protect_end") and de is not None and de <= days:
            if a["category"] == "商标":
                tm_renew.append(dict(base, **{"date": a["protect_end"], "days": de,
                                              "renew_start": _d(a["protect_end"]).replace(
                                                  year=_d(a["protect_end"]).year - 1).isoformat()}))
            elif a["category"] == "数据知识产权":
                data_renew.append(dict(base, **{"date": a["protect_end"], "days": de}))
            elif a["category"] == "专利":
                patent_expire.append(dict(base, **{"date": a["protect_end"], "days": de}))
    key = lambda x: x["days"]
    return ok({
        "days": days,
        "overdue": sorted(overdue, key=key),
        "fee_due": sorted(fee_due, key=key),
        "tm_renew": sorted(tm_renew, key=key),
        "data_renew": sorted(data_renew, key=key),
        "patent_expire": sorted(patent_expire, key=key),
    })


def stats_distribution(conn, q=None):
    rows = _all_assets(conn)
    patent_type, tm_class, cr_type, tech_field, data_type = {}, {}, {}, {}, {}
    for a in rows:
        if a["category"] == "专利":
            k = a["sub_type"] or "未分类"
            patent_type[k] = patent_type.get(k, 0) + 1
        if a["category"] == "商标":
            nums = re.findall(r"第\s*(\d+)\s*类", a.get("class_no") or "")
            k = "第 %s 类" % "、".join(nums) if nums else (a.get("class_no") or "未分类")
            tm_class[k] = tm_class.get(k, 0) + 1
        if a["category"] == "著作权":
            k = a["sub_type"] or "未分类"
            cr_type[k] = cr_type.get(k, 0) + 1
        if a["category"] == "数据知识产权":
            k = a["sub_type"] or "未分类"
            data_type[k] = data_type.get(k, 0) + 1
        tf = (a.get("tech_field") or "未填写").split("/")[0].strip()
        tech_field[tf] = tech_field.get(tf, 0) + 1
    srt = lambda d: sorted([{"name": k, "value": v} for k, v in d.items()], key=lambda x: -x["value"])
    return ok({"patent_type": srt(patent_type), "tm_class": srt(tm_class),
               "copyright_type": srt(cr_type), "data_type": srt(data_type),
               "tech_field": srt(tech_field)[:12]})


def stats_analysis(conn, q=None):
    """综合分析结论与布局评价"""
    rows = _all_assets(conn)
    ov = stats_overview(conn)["data"]
    total = len(rows)
    conclusions, scores, suggestions = [], {}, []

    cat = {c["name"]: c["value"] for c in ov["by_category"]}
    patents = sum(v for k, v in cat.items() if k == "专利")
    inv = sum(1 for a in rows if a["sub_type"] == "发明专利")
    um = sum(1 for a in rows if a["sub_type"] == "实用新型专利")
    des = sum(1 for a in rows if a["sub_type"] == "外观设计专利")
    sw = sum(1 for a in rows if a["sub_type"] == "软件著作权")
    work = sum(1 for a in rows if a["sub_type"] == "作品著作权")
    tm = sum(1 for a in rows if a["category"] == "商标")
    data = sum(1 for a in rows if a["category"] == "数据知识产权")

    # 1. 总量与结构
    conclusions.append(
        "企业现有知识产权 %d 件，其中专利 %d 件（发明 %d、实用新型 %d、外观设计 %d）、"
        "著作权 %d 件（软件著作权 %d、作品著作权 %d）、商标 %d 件、数据知识产权 %d 件。"
        "权利有效率 %.1f%%，处于审查/申请阶段 %d 件，已失效或驳回 %d 件。"
        % (total, patents, inv, um, des, sw + work, sw, work, tm, data,
           ov["valid_rate"], ov["pending"], ov["dead"]))

    # 2. 专利质量结构
    inv_ratio = inv / patents * 100 if patents else 0
    if inv_ratio >= 50:
        ev = "发明专利占专利总量 %.0f%%，处于较好水平，技术壁垒相对较高。" % inv_ratio
        scores["专利质量"] = 85
    elif inv_ratio >= 35:
        ev = "发明专利占专利总量 %.0f%%，结构基本合理，但仍有提升空间。" % inv_ratio
        scores["专利质量"] = 70
    else:
        ev = "发明专利占专利总量仅 %.0f%%，实用新型与外观设计占比偏高，权利稳定性与技术壁垒偏弱。" % inv_ratio
        scores["专利质量"] = 55
        suggestions.append("提升发明专利申报比例，对核心技术采用发明与实用新型双报策略。")
    conclusions.append("专利结构评价：" + ev)

    # 3. 外围布局
    core = sum(1 for a in rows if a["sub_type"] == "发明专利" and a["status"] in ("有效", "已授权", "质押", "许可"))
    ratio = (um + des) / core if core else 0
    if core and ratio >= 2:
        conclusions.append("外围布局评价：核心有效发明专利 %d 件，实用新型与外观设计合计 %d 件，"
                           "外围/核心比为 %.1f:1，已达到推荐的 2:1 水平，核心专利被绕开难度较高。"
                           % (core, um + des, ratio))
        scores["外围布局"] = 82
    elif core:
        conclusions.append("外围布局评价：核心有效发明专利 %d 件，外围专利 %d 件，比值 %.1f:1，"
                           "低于推荐的 2:1，建议在结构实现、参数优选、应用场景三个方向补充外围申请。"
                           % (core, um + des, ratio))
        scores["外围布局"] = 60
        suggestions.append("围绕核心发明专利补充外围实用新型与外观设计申请，形成三层保护。")

    # 4. 保护维度完整性
    dims = []
    if patents: dims.append("专利")
    if sw or work: dims.append("著作权")
    if tm: dims.append("商标")
    if data: dims.append("数据知识产权")
    if len(dims) == 4:
        conclusions.append("保护维度评价：已形成\"专利 + 著作权 + 商标 + 数据知识产权\"四维保护体系，"
                           "覆盖技术、代码、品牌与数据资产，维度完整性良好。")
        scores["维度完整性"] = 90
    else:
        miss = [x for x in ["专利", "著作权", "商标", "数据知识产权"] if x not in dims]
        conclusions.append("保护维度评价：当前覆盖 %s，尚缺 %s，"
                           "建议补齐空白维度以形成完整的权利组合。" % ("、".join(dims), "、".join(miss)))
        scores["维度完整性"] = 60
        suggestions.append("补齐 %s 方向的知识产权登记与申请。" % "、".join(miss))

    # 5. 维持风险
    risky = [a for a in rows if a["status"] in ("年费滞纳", "撤三风险", "诉讼中")]
    fee_soon = [a for a in rows if a["status"] not in DEAD_STATUS and a.get("fee_paid") == 0
                and _days(a.get("next_fee_date")) is not None
                and -1 <= _days(a.get("next_fee_date")) <= 90]
    data_dead = [a for a in rows if a["category"] == "数据知识产权"
                 and _days(a.get("protect_end")) is not None and _days(a["protect_end"]) < 0]
    if risky or fee_soon or data_dead:
        conclusions.append(
            "维持风险预警：当前有 %d 件权利处于滞纳/撤三/诉讼状态，%d 件年费将在 90 天内到期，"
            "%d 件数据知识产权登记已过有效期。上述事项若未及时处置，"
            "将直接导致权利终止或登记失效。" % (len(risky), len(fee_soon), len(data_dead)))
        scores["维持管理"] = 55
        suggestions.append("建立年费、续展、登记有效期的三级预警台账，在到期前 90 天自动提醒。")
    else:
        conclusions.append("维持风险预警：未发现年费逾期、撤三与登记失效事项，权利维持状态良好。")
        scores["维持管理"] = 88

    # 6. 地域布局
    overseas = [a for a in rows if (a.get("region") or "国内") != "国内"]
    if overseas:
        conclusions.append("地域布局评价：现有 %d 件权利涉及涉外保护，"
                           "建议继续按目标市场优先级扩大 PCT 与马德里体系布局。" % len(overseas))
        scores["地域布局"] = 70
    else:
        conclusions.append("地域布局评价：全部 %d 件权利的保护地域均为国内，海外布局为零。"
                           "若存在产品出口或技术服务出海计划，将面临被抢注与侵权双重风险。" % total)
        scores["地域布局"] = 40
        suggestions.append("按目标市场通过 PCT 与马德里体系启动海外布局，出口前完成 FTO 检索。")

    # 7. 运营转化
    operating = [a for a in rows if a["status"] in ("质押", "许可")]
    if operating:
        conclusions.append("运营转化评价：现有 %d 件权利已进入质押或许可运营状态，"
                           "知识产权由成本项向资产项转化，建议进一步探索作价入股与证券化路径。"
                           % len(operating))
        scores["运营转化"] = 75
    else:
        conclusions.append("运营转化评价：现有权利均未开展质押、许可等运营行为，"
                           "知识产权仍以防御性持有为主，资产价值未充分释放。")
        scores["运营转化"] = 45
        suggestions.append("筛选稳定性高的核心专利开展质押融资与许可，推动知识产权资产化运营。")

    # 8. 时间趋势
    tr = stats_trend(conn)["data"]
    if tr["years"]:
        recent = tr["apply"][-3:]
        early = tr["apply"][:3]
        trend_up = sum(recent) >= sum(early)
        conclusions.append(
            "申请趋势评价：%s 年累计申请 %d 件，近三年申请 %d 件，"
            "研发产出呈%s态势。" % (tr["years"][0] + "—" + tr["years"][-1], sum(tr["apply"]),
                                sum(recent), "上升" if trend_up else "放缓"))
        scores["创新持续性"] = 80 if trend_up else 60
        if not trend_up:
            suggestions.append("近三年申请量较前期放缓，建议加强研发项目专利挖掘节点的管控。")

    overall = round(sum(scores.values()) / max(len(scores), 1))
    suggestions = list(dict.fromkeys(suggestions))[:8]
    return ok({"conclusions": conclusions, "scores": scores, "overall": overall,
               "suggestions": suggestions,
               "summary": {"total": total, "patents": patents, "copyright": sw + work,
                           "trademark": tm, "data_ip": data, "valid_rate": ov["valid_rate"]}})


# --------------------------------------------------------------------------
# 战略
# --------------------------------------------------------------------------
def list_strategies(conn, q=None):
    q = q or {}
    module = q.get("module", "").strip()
    kw = q.get("keyword", "").strip()
    level = q.get("risk_level", "").strip()
    where, args = [], []
    if module:
        where.append("module=?"); args.append(module)
    if level:
        where.append("risk_level=?"); args.append(level)
    if kw:
        where.append("(title LIKE ? OR content LIKE ? OR actions LIKE ? OR category LIKE ?)")
        args += [f"%{kw}%"] * 4
    sql = "SELECT * FROM strategies"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY CASE risk_level WHEN '高' THEN 0 WHEN '中' THEN 1 ELSE 2 END, id"
    rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    return ok({"items": rows, "total": len(rows)})


def create_strategy(conn, body):
    if not (body.get("title") or "").strip():
        return err("标题不能为空")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    d = {k: body.get(k, "") for k in ["module", "title", "category", "risk_level", "content",
                                      "actions", "owner", "deadline", "status"]}
    d["module"] = d["module"] if d["module"] in ("avoid", "risk") else "risk"
    d["risk_level"] = d["risk_level"] if d["risk_level"] in LEVELS else "中"
    d["status"] = d["status"] or "待启动"
    d["source"] = "manual"
    d["created_at"] = now
    d["updated_at"] = now
    cols = ",".join(d.keys())
    ph = ",".join("?" * len(d))
    cur = conn.execute(f"INSERT INTO strategies ({cols}) VALUES ({ph})", list(d.values()))
    conn.commit()
    return ok(dict(conn.execute("SELECT * FROM strategies WHERE id=?", (cur.lastrowid,)).fetchone()))


def update_strategy(conn, sid, body):
    r = conn.execute("SELECT * FROM strategies WHERE id=?", (sid,)).fetchone()
    if not r:
        return err("条目不存在", 404)
    fields = ["module", "title", "category", "risk_level", "content", "actions", "owner",
              "deadline", "status"]
    sets, vals = [], []
    for f in fields:
        if f in body:
            sets.append(f"{f}=?"); vals.append(body[f])
    vals.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if sets:
        conn.execute(f"UPDATE strategies SET {','.join(sets)}, updated_at=? WHERE id=?",
                     vals + [sid])
        conn.commit()
    return ok(dict(conn.execute("SELECT * FROM strategies WHERE id=?", (sid,)).fetchone()))


def delete_strategy(conn, sid):
    r = conn.execute("SELECT id FROM strategies WHERE id=?", (sid,)).fetchone()
    if not r:
        return err("条目不存在", 404)
    conn.execute("DELETE FROM strategies WHERE id=?", (sid,))
    conn.commit()
    return ok({"id": sid})


def rebuild_strategy(conn, body=None):
    n = strategy_mod.rebuild(conn)
    return ok({"rebuilt": n})


# --------------------------------------------------------------------------
# 数据管理：导出 / 导入 / 重置
# --------------------------------------------------------------------------
def export_data(conn):
    data = {
        "version": 1,
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "company": dict(conn.execute("SELECT * FROM company WHERE id=1").fetchone() or {}),
        "assets": [],
        "strategies": [dict(r) for r in conn.execute("SELECT * FROM strategies")],
    }
    for r in conn.execute("SELECT * FROM assets ORDER BY id"):
        a = _row2dict(r)
        a["logs"] = [dict(x) for x in conn.execute(
            "SELECT * FROM status_logs WHERE asset_id=? ORDER BY id", (a["id"],))]
        a["fees"] = [dict(x) for x in conn.execute(
            "SELECT * FROM fee_records WHERE asset_id=? ORDER BY id", (a["id"],))]
        data["assets"].append(a)
    return data


def import_data(conn, payload):
    if not isinstance(payload, dict) or "assets" not in payload:
        return err("导入数据格式不正确")
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM fee_records")
        cur.execute("DELETE FROM status_logs")
        cur.execute("DELETE FROM strategies")
        cur.execute("DELETE FROM assets")
        if payload.get("company"):
            c = {k: v for k, v in payload["company"].items() if k != "id"}
            if c:
                cols = ",".join(["id"] + list(c.keys()))
                ph = ",".join(["?"] * (len(c) + 1))
                cur.execute(f"REPLACE INTO company ({cols}) VALUES ({ph})", [1] + list(c.values()))
        for a in payload["assets"]:
            logs, fees = a.pop("logs", []), a.pop("fees", [])
            a.pop("id", None)
            a["scope_items"] = json.dumps(a.get("scope_items") or [], ensure_ascii=False)
            cols = ",".join(a.keys())
            ph = ",".join("?" * len(a))
            cur.execute(f"INSERT INTO assets ({cols}) VALUES ({ph})", list(a.values()))
            aid = cur.lastrowid
            for lg in logs:
                lg = {k: v for k, v in lg.items() if k != "id"}
                lg["asset_id"] = aid
                cols = ",".join(lg.keys())
                ph = ",".join("?" * len(lg))
                cur.execute(f"INSERT INTO status_logs ({cols}) VALUES ({ph})", list(lg.values()))
            for fe in fees:
                fe = {k: v for k, v in fe.items() if k != "id"}
                fe["asset_id"] = aid
                cols = ",".join(fe.keys())
                ph = ",".join("?" * len(fe))
                cur.execute(f"INSERT INTO fee_records ({cols}) VALUES ({ph})", list(fe.values()))
        for s in payload.get("strategies", []):
            s.pop("id", None)
            cols = ",".join(s.keys())
            ph = ",".join("?" * len(s))
            cur.execute(f"INSERT INTO strategies ({cols}) VALUES ({ph})", list(s.values()))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return err("导入失败：%s" % e)
    return ok({"assets": len(payload["assets"]),
               "strategies": len(payload.get("strategies", []))})


def reset_data(conn, body=None):
    mode = (body or {}).get("mode", "demo")
    cur = conn.cursor()
    cur.execute("DELETE FROM fee_records")
    cur.execute("DELETE FROM status_logs")
    cur.execute("DELETE FROM strategies")
    cur.execute("DELETE FROM assets")
    cur.execute("DELETE FROM company")
    conn.commit()
    if mode == "demo":
        import db as db_mod
        db_mod._seed_company(conn)
        db_mod._seed_assets(conn)
        db_mod._seed_strategies(conn)
        conn.commit()
        strategy_mod.rebuild(conn)
    return ok({"mode": mode,
               "assets": conn.execute("SELECT COUNT(*) c FROM assets").fetchone()["c"],
               "strategies": conn.execute("SELECT COUNT(*) c FROM strategies").fetchone()["c"]})


def get_meta(conn, q=None):
    return ok({"categories": CATEGORIES, "statuses": STATUSES, "departments": DEPARTMENTS,
               "regions": REGIONS, "levels": LEVELS, "modules": MODULE_NAMES,
               "today": TODAY.isoformat()})


# --------------------------------------------------------------------------
# 期限日历
# --------------------------------------------------------------------------
def _level(days, done=False):
    if done:
        return "done"
    if days is None:
        return "low"
    if days < 0:
        return "overdue"
    if days <= 30:
        return "high"
    if days <= 90:
        return "medium"
    return "low"


def calendar(conn, q=None):
    q = q or {}
    try:
        year = int(q.get("year") or TODAY.year)
        month = int(q.get("month") or TODAY.month)
    except Exception:
        year, month = TODAY.year, TODAY.month
    if month < 1:
        month, year = 12, year - 1
    if month > 12:
        month, year = 1, year + 1

    rows = _all_assets(conn)
    items = []
    for a in rows:
        if a["status"] in ("失效", "终止", "驳回", "撤回"):
            continue
        base = {"id": a["id"], "name": a["name"], "category": a["category"],
                "sub_type": a["sub_type"], "no": a.get("grant_no") or a.get("app_no") or "",
                "department": a["department"], "status": a["status"]}
        # 年费 / 续展缴费
        if a.get("next_fee_date"):
            d = _days(a["next_fee_date"])
            items.append(dict(base, kind="年费缴纳", date=a["next_fee_date"], days=d,
                              note="第 %s 年度" % (a.get("fee_year") or "—"),
                              level=_level(d, bool(a.get("fee_paid")))))
        # 保护期届满 / 续展
        if a.get("protect_end"):
            d = _days(a["protect_end"])
            if a["category"] == "商标":
                kind, note = "商标续展截止", "专用权届满，续展窗口为届满前 12 个月"
            elif a["category"] == "数据知识产权":
                kind, note = "登记续展截止", "登记证书有效期 2 年，需办理续展"
            else:
                kind, note = "保护期届满", "技术方案进入公有领域"
            items.append(dict(base, kind=kind, date=a["protect_end"], days=d, note=note,
                              level=_level(d)))
        # 发明专利提实审期限
        if a["sub_type"] == "发明专利" and a["status"] == "申请中" and a.get("app_date"):
            ad = _d(a["app_date"])
            if ad:
                dl = ad.replace(year=ad.year + 3)
                d = _days(dl.isoformat())
                items.append(dict(base, kind="提实审期限", date=dl.isoformat(), days=d,
                                  note="实质审查请求应自申请日起 3 年内提出",
                                  level=_level(d)))

    in_month, overdue = [], []
    for it in items:
        if it["days"] is not None and it["days"] < 0 and it["level"] == "overdue":
            overdue.append(it)
        if (it.get("date") or "")[:7] == "%04d-%02d" % (year, month):
            in_month.append(it)
    in_month.sort(key=lambda x: (x["date"], 0 if x["level"] == "overdue" else 1))
    overdue.sort(key=lambda x: x["date"])

    days_map = {}
    for it in in_month:
        days_map.setdefault(it["date"], []).append(it)

    summary = Counter(x["level"] for x in in_month)
    return ok({
        "year": year, "month": month,
        "days": days_map,
        "list": in_month,
        "overdue": overdue[:20],
        "summary": {"total": len(in_month), "overdue": summary.get("overdue", 0),
                    "high": summary.get("high", 0), "medium": summary.get("medium", 0),
                    "low": summary.get("low", 0), "done": summary.get("done", 0),
                    "overdue_total": len(overdue)},
    })


# --------------------------------------------------------------------------
# 深度分析
# --------------------------------------------------------------------------
IPC_SECTIONS = {
    "A": "A 人类生活必需", "B": "B 作业与运输", "C": "C 化学与冶金",
    "D": "D 纺织与造纸", "E": "E 固定建筑物", "F": "F 机械工程·照明·加热",
    "G": "G 物理", "H": "H 电学",
}


def stats_deep(conn, q=None):
    rows = _all_assets(conn)

    # 发明人 / 作者排行（排除法人主体，仅统计自然人）
    co = conn.execute("SELECT name FROM company WHERE id=1").fetchone()
    co_name = (co["name"] if co else "") or ""
    people = Counter()
    for a in rows:
        applicant = (a.get("applicant") or "").strip()
        for n in re.split(r"[;；,，、/]\s*", a.get("creators") or ""):
            n = n.strip()
            if not n or n in ("—", "-", "无"):
                continue
            if n == applicant or n == co_name:
                continue                      # 法人作品的权利人不计入发明人
            # 法人主体与内设部门不计入自然人发明人
            if re.search(r"(公司|研究院|大学|学院|事务所|集团|中心|部门|事业部|厂)$|公司|（法人", n):
                continue
            people[n] += 1
    inventors = [{"name": k, "value": v} for k, v in people.most_common(10)]

    # 分类号分布：IPC 部 + 小类，兼顾洛迦诺与尼斯
    sec, cls, nice = Counter(), Counter(), Counter()
    for a in rows:
        cn = a.get("class_no") or ""
        lo = re.findall(r"洛迦诺\s*([\d\-]+)", cn)
        ni = re.findall(r"第\s*(\d+)\s*类", cn)
        ipc_codes = re.findall(r"\b([A-H]\d{2}[A-Z]?)\b", cn)
        for x in lo:
            cls["洛迦诺 " + x] += 1
        for x in ni:
            nice["第 %s 类" % x] += 1
        for c in ipc_codes:
            sec[c[0]] += 1
            cls[c[:4]] += 1
    ipc_section = [{"name": IPC_SECTIONS.get(k, k), "value": v}
                   for k, v in sorted(sec.items(), key=lambda x: -x[1])]
    ipc_class = [{"name": k, "value": v} for k, v in cls.most_common(10)]

    # 专利年龄分布
    age_buckets = [("未满 3 年", 0, 3), ("3–5 年", 3, 5), ("5–10 年", 5, 10),
                   ("10–15 年", 10, 15), ("15 年以上", 15, 999)]
    ages = Counter()
    for a in rows:
        if a["category"] != "专利":
            continue
        ad = _d(a.get("app_date"))
        if not ad:
            continue
        y = (TODAY - ad).days / 365.25
        for nm, lo, hi in age_buckets:
            if lo <= y < hi:
                ages[nm] += 1
                break
    patent_age = [{"name": nm, "value": ages.get(nm, 0)} for nm, _, _ in age_buckets]

    # 申请—授权转化率（按申请年 cohort）
    cohort = {}
    for a in rows:
        if a["category"] != "专利":
            continue
        y = (a.get("app_date") or "")[:4]
        if not y.isdigit():
            continue
        c = cohort.setdefault(int(y), {"total": 0, "granted": 0})
        c["total"] += 1
        if a.get("grant_date"):
            c["granted"] += 1
    ys = sorted(cohort.keys())
    grant_rate = {
        "years": [str(y) for y in ys],
        "apply": [cohort[y]["total"] for y in ys],
        "granted": [cohort[y]["granted"] for y in ys],
        "rate": [round(cohort[y]["granted"] / cohort[y]["total"] * 100, 1) for y in ys],
    }

    # 代理机构分布
    ag = Counter(a.get("agency") or "未填写" for a in rows)
    agency = [{"name": k, "value": v} for k, v in ag.most_common(8)]

    # 有效 / 失效构成（按大类）
    cats = list(CATEGORIES.keys())
    stack = {
        "categories": cats,
        "valid": [sum(1 for a in rows if a["category"] == c and a["status"] in VALID_STATUS) for c in cats],
        "pending": [sum(1 for a in rows if a["category"] == c and a["status"] in PENDING_STATUS) for c in cats],
        "dead": [sum(1 for a in rows if a["category"] == c and a["status"] in DEAD_STATUS) for c in cats],
    }

    return ok({"inventors": inventors, "ipc_section": ipc_section, "ipc_class": ipc_class,
               "nice_class": [{"name": k, "value": v} for k, v in nice.most_common(10)],
               "patent_age": patent_age, "grant_rate": grant_rate,
               "agency": agency, "stack": stack})


# --------------------------------------------------------------------------
# Excel / CSV 导入导出
# --------------------------------------------------------------------------
CSV_FIELDS = [
    ("category", "知识产权类型"), ("sub_type", "子类型"), ("name", "名称"),
    ("app_no", "申请号/登记申请号"), ("grant_no", "授权号/登记号/注册号"),
    ("app_date", "申请日"), ("grant_date", "授权日/登记日/注册日"),
    ("applicant", "申请人/权利人"), ("creators", "发明人/作者/设计人"),
    ("agency", "代理机构"), ("class_no", "分类号"), ("tech_field", "技术领域/商品类别"),
    ("department", "归属部门"), ("region", "保护地域"), ("status", "当前状态"),
    ("status_date", "状态更新日期"), ("fee_year", "年费年度"), ("fee_paid", "本期已缴"),
    ("next_fee_date", "下一年费/续展截止日"), ("protect_start", "保护期起始日"),
    ("protect_end", "保护期届满日"), ("scope_text", "保护范围描述"),
    ("scope_items", "保护范围要点"), ("key_points", "核心要点"),
    ("rival_ref", "竞争对手/参照专利族"), ("remark", "备注"),
]
CSV_HEADER = [t for _, t in CSV_FIELDS]
CSV_KEYS = [k for k, _ in CSV_FIELDS]

SAMPLE_ROW = [
    "专利", "发明专利", "示例：一种基于负压反馈的自适应抓取控制方法",
    "202610123456.7", "ZL202610123456.7", "2026-01-15", "2026-08-01",
    "衢州量智科技有限公司", "张三; 李四", "XX专利代理事务所",
    "B25J 15/06 (2006.01)", "智能装备", "研发中心", "国内", "有效", "2026-08-01",
    "1", "未缴", "2027-01-15", "2026-01-15", "2046-01-14",
    "权利要求 1：……", "独立权利要求 1 项 | 从属权利要求 10 项", "负压变化率判漏",
    "—", "备注信息",
]


def _export_assets(conn):
    out = []
    for r in conn.execute("SELECT * FROM assets ORDER BY category, id"):
        a = _row2dict(r)
        a["scope_items"] = " | ".join(a.get("scope_items") or [])
        a["fee_paid"] = "已缴" if a.get("fee_paid") else "未缴"
        a["scope_text"] = (a.get("scope_text") or "").replace("\n", " ")
        out.append(a)
    return out


def export_csv(conn, q=None):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_HEADER)
    for a in _export_assets(conn):
        w.writerow([a.get(k, "") if a.get(k) is not None else "" for k in CSV_KEYS])
    name = "知识产权台账-%s.csv" % TODAY.isoformat()
    return ok({"csv": buf.getvalue(), "filename": name, "count": len(_export_assets(conn))})


def _xesc(s):
    return (str(s if s is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def export_xls(conn, q=None):
    """生成 SpreadsheetML 2003 工作簿（.xls），Excel / WPS 可直接打开，无需第三方库"""
    data = _export_assets(conn)
    company = conn.execute("SELECT * FROM company WHERE id=1").fetchone()
    co = dict(company) if company else {}

    def sheet(name, rows, widths):
        h = ['<Worksheet ss:Name="%s"><Table>' % _xesc(name)]
        h.append('<Column ss:Width="%d"/>' % 40)
        for w in widths:
            h.append('<Column ss:Width="%d"/>' % w)
        for ri, row in enumerate(rows):
            style = ' ss:StyleID="hdr"' if ri == 0 else ""
            h.append("<Row%s>" % style)
            for cell in row:
                is_num = isinstance(cell, (int, float)) and not isinstance(cell, bool)
                t = "Number" if is_num else "String"
                h.append('<Cell%s><Data ss:Type="%s">%s</Data></Cell>' % ("" if ri else ' ss:StyleID="hdr"', t, _xesc(cell)))
            h.append("</Row>")
        h.append("</Table><WorksheetOptions xmlns=\"urn:schemas-microsoft-com:office:excel\">"
                 "<FreezePanes/><SplitHorizontal>1</SplitHorizontal>"
                 "<TopRowBottomPane>1</TopRowBottomPane><ActivePane>2</ActivePane>"
                 "</WorksheetOptions></Worksheet>")
        return "".join(h)

    main = [CSV_HEADER]
    for a in data:
        main.append([a.get(k, "") if a.get(k) is not None else "" for k in CSV_KEYS])
    widths = [90] * len(CSV_HEADER)

    stat_rows = [["统计项", "数值"]]
    ov = stats_overview(conn)["data"]
    stat_rows += [
        ["企业名称", co.get("name", "")],
        ["统一社会信用代码", co.get("credit_code", "")],
        ["台账导出日期", TODAY.isoformat()],
        ["知识产权总量", ov["total"]],
        ["有效权利", ov["valid"]],
        ["审查 / 申请中", ov["pending"]],
        ["失效 / 驳回", ov["dead"]],
        ["权利有效率", "%.1f%%" % ov["valid_rate"]],
        ["风险预警项", ov["risk"]],
    ]
    for item in ov["by_category"]:
        stat_rows.append(["　" + item["name"], item["value"]])
    for item in ov["by_status"]:
        stat_rows.append(["　状态：" + item["name"], item["value"]])

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<?mso-application progid="Excel.Sheet"?>\n'
           '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" '
           'xmlns:o="urn:schemas-microsoft-com:office:office" '
           'xmlns:x="urn:schemas-microsoft-com:office:excel" '
           'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
           '<Styles>'
           '<Style ss:ID="hdr"><Font ss:Bold="1" ss:Color="#1F3864"/>'
           '<Interior ss:Color="#DCE6F1" ss:Pattern="Solid"/>'
           '<Alignment ss:Vertical="Center" ss:WrapText="1"/></Style>'
           '</Styles>')
    xml += sheet("统计汇总", stat_rows, [200])
    xml += sheet("知识产权台账", main, widths)
    xml += "</Workbook>"
    return ok({"xml": xml, "filename": "知识产权台账-%s.xls" % TODAY.isoformat(),
               "count": len(data)})


def template_csv(conn=None, q=None):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_HEADER)
    w.writerow(SAMPLE_ROW)
    return ok({"csv": buf.getvalue(), "filename": "知识产权导入模板.csv",
               "fields": CSV_HEADER,
               "tips": "填写说明：①「知识产权类型」须为 专利 / 著作权 / 数据知识产权 / 商标；"
                       "②「子类型」须与所选类型匹配，如发明专利、实用新型专利、外观设计专利、"
                       "软件著作权、作品著作权、数据资源登记、数据产品登记、注册商标；"
                       "③日期统一使用 YYYY-MM-DD 格式；④「保护范围要点」多项之间用 | 分隔；"
                       "⑤「本期已缴」填 已缴 / 未缴；⑥「申请号/登记申请号」相同视为同一条记录，"
                       "导入时按追加更新处理；⑦「名称」为必填项。"})


def import_csv(conn, body=None):
    body = body or {}
    text = body.get("csv") or ""
    mode = body.get("mode", "append")
    if not text.strip():
        return err("CSV 内容为空")

    # 容错：跳过 UTF-8 BOM，按表头定位列
    if text and text[0] == "\ufeff":
        text = text[1:]
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any((c or "").strip() for c in r)]
    if len(rows) < 2:
        return err("CSV 至少需要表头与一行数据")

    header = [(c or "").strip() for c in rows[0]]
    rev = {}
    for k, t in CSV_FIELDS:
        rev[t] = k
        rev[k] = k
    idx = {}
    for i, h in enumerate(header):
        if h in rev:
            idx[rev[h]] = i
    if "name" not in idx:
        return err("未识别到「名称」列，请使用系统导出的模板")

    created = updated = skipped = 0
    errors = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if mode == "replace":
        conn.execute("DELETE FROM fee_records")
        conn.execute("DELETE FROM status_logs")
        conn.execute("DELETE FROM assets")
        conn.commit()

    exist_no = {}
    exist_name = {}
    for r in conn.execute("SELECT id, app_no, name FROM assets"):
        if r["app_no"]:
            exist_no[r["app_no"].strip()] = r["id"]
        exist_name[r["name"].strip()] = r["id"]

    for ri, row in enumerate(rows[1:], start=2):
        def cell(key):
            i = idx.get(key)
            return (row[i].strip() if i is not None and i < len(row) else "")

        name = cell("name")
        if not name:
            skipped += 1
            errors.append({"row": ri, "msg": "名称为空，已跳过"})
            continue
        cat = cell("category") or "专利"
        if cat not in CATEGORIES:
            skipped += 1
            errors.append({"row": ri, "name": name, "msg": "知识产权类型「%s」不合法" % cat})
            continue
        sub = cell("sub_type")
        if sub and sub not in CATEGORIES[cat]:
            errors.append({"row": ri, "name": name,
                           "msg": "子类型「%s」与类型「%s」不匹配，已按类型默认处理" % (sub, cat)})
            sub = ""
        if not sub:
            sub = CATEGORIES[cat][0]

        paid_raw = cell("fee_paid")
        rec = {
            "category": cat, "sub_type": sub, "name": name,
            "app_no": cell("app_no"), "grant_no": cell("grant_no"),
            "app_date": cell("app_date"), "grant_date": cell("grant_date"),
            "applicant": cell("applicant"), "creators": cell("creators"),
            "agency": cell("agency"), "class_no": cell("class_no"),
            "tech_field": cell("tech_field"), "department": cell("department"),
            "region": cell("region") or "国内",
            "status": cell("status") or "申请中", "status_date": cell("status_date"),
            "fee_year": cell("fee_year") or 0,
            "fee_paid": 1 if paid_raw in ("已缴", "是", "1", "Y", "y", "已缴纳") else 0,
            "next_fee_date": cell("next_fee_date"),
            "protect_start": cell("protect_start"), "protect_end": cell("protect_end"),
            "scope_text": cell("scope_text"),
            "scope_items": [s.strip() for s in re.split(r"[|｜]", cell("scope_items")) if s.strip()],
            "key_points": cell("key_points"), "rival_ref": cell("rival_ref"),
            "remark": cell("remark"),
        }
        key = (rec["app_no"] or "").strip()
        aid = exist_no.get(key) if key else exist_name.get(name)

        if aid:
            data = _norm_asset_body({**dict(conn.execute(
                "SELECT * FROM assets WHERE id=?", (aid,)).fetchone()), **rec})
            data["updated_at"] = now
            sets = ",".join(f"{k}=?" for k in data.keys())
            conn.execute(f"UPDATE assets SET {sets} WHERE id=?", list(data.values()) + [aid])
            updated += 1
        else:
            data = _norm_asset_body(rec)
            data["created_at"] = now
            data["updated_at"] = now
            cols = ",".join(data.keys())
            ph = ",".join("?" * len(data))
            cur = conn.execute(f"INSERT INTO assets ({cols}) VALUES ({ph})", list(data.values()))
            aid = cur.lastrowid
            created += 1
            if key:
                exist_no[key] = aid
            exist_name[name] = aid
            if rec["status"]:
                conn.execute(
                    "INSERT INTO status_logs(asset_id,change_date,old_status,new_status,note,created_at)"
                    " VALUES (?,?,?,?,?,?)",
                    (aid, rec.get("status_date") or rec.get("app_date") or TODAY.isoformat(),
                     "", rec["status"], "批量导入建档", now))
    conn.commit()
    return ok({"created": created, "updated": updated, "skipped": skipped,
               "errors": errors[:30], "error_total": len(errors)})
