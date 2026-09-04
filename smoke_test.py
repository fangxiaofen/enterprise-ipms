# -*- coding: utf-8 -*-
"""接口冒烟测试：验证增删改查、关联记录、统计与数据管理接口"""
import json
import urllib.request
import urllib.error
from urllib.parse import quote

BASE = "http://127.0.0.1:8770/api"
PY = None


def call(method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + quote(path, safe="/?&="), data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def show(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + ((" -> " + str(extra)) if extra else ""))
    return cond


results = []


def T(name, cond, extra=""):
    results.append(show(name, cond, extra))


def main():
    print("== 资产 CRUD ==")
    s, d = call("GET", "/assets?page_size=3")
    total0 = d["data"]["total"]
    T("列表接口", s == 200 and total0 > 0, "total=%d" % total0)

    s, d = call("POST", "/assets", {
        "category": "专利", "sub_type": "发明专利", "name": "冒烟测试专利XYZ",
        "app_no": "202699999999.9", "app_date": "2026-01-15",
        "applicant": "衢州量智科技有限公司", "status": "审查中",
        "scope_items": ["要点A", "要点B"], "protect_end": "2046-01-14"})
    aid = d.get("data", {}).get("id")
    T("新建资产", s == 200 and aid, "id=%s items=%s" % (aid, d.get("data", {}).get("scope_items")))

    s, d = call("PUT", "/assets/%s" % aid, {
        "status": "已授权", "grant_no": "ZL202699999999.9", "grant_date": "2026-08-01",
        "next_fee_date": "2027-01-15", "fee_paid": 0, "fee_year": 1})
    da = d.get("data", {})
    T("更新并自动记状态变更", s == 200 and da.get("status") == "已授权" and len(da.get("logs", [])) == 2,
      [(l["old_status"], l["new_status"]) for l in da.get("logs", [])])

    s, d = call("POST", "/assets/%s/fees" % aid,
                {"year": 1, "amount": 900, "due_date": "2027-01-15",
                 "paid": 1, "paid_date": "2026-12-20", "note": "第1年"})
    da = d.get("data", {})
    T("添加年费记录", s == 200 and len(da.get("fees", [])) == 1 and da.get("fee_paid") == 1,
      "next_fee=%s paid=%s" % (da.get("next_fee_date"), da.get("fee_paid")))

    s, d = call("PUT", "/assets/%s" % aid, {"status": "有效"})
    T("再次变更状态", s == 200 and d["data"]["status"] == "有效")

    s, d = call("GET", "/assets?keyword=冒烟测试")
    T("关键词搜索", s == 200 and d["data"]["total"] == 1, d["data"]["total"])
    s, d = call("GET", "/assets?category=专利&sub_type=发明专利")
    T("类型+子类型筛选", s == 200 and all(a["sub_type"] == "发明专利" for a in d["data"]["items"]),
      d["data"]["total"])

    s, d = call("DELETE", "/assets/%s" % aid)
    T("删除资产", s == 200)
    s, d = call("GET", "/assets?keyword=冒烟测试")
    T("删除后搜索为空", d["data"]["total"] == 0)

    print("== 企业信息 ==")
    s, d = call("GET", "/company")
    T("读取企业信息", s == 200 and d["data"].get("name"), d["data"].get("name"))
    s, d = call("PUT", "/company", {"contact": "测试联系人"})
    T("修改企业信息", s == 200 and d["data"]["contact"] == "测试联系人")
    call("PUT", "/company", {"contact": "方晓汾"})

    print("== 统计接口 ==")
    for path, key in [("/stats/overview", "total"), ("/stats/trend", "years"),
                      ("/stats/expiry", "fee_due"), ("/stats/distribution", "patent_type"),
                      ("/stats/analysis", "conclusions")]:
        s, d = call("GET", path)
        okv = s == 200 and key in d.get("data", {})
        extra = ""
        if path == "/stats/overview":
            dd = d["data"]
            extra = "total=%d valid=%d risk=%d by_category=%s" % (
                dd["total"], dd["valid"], dd["risk"],
                [(x["name"], x["value"]) for x in dd["by_category"]])
        elif path == "/stats/expiry":
            dd = d["data"]
            extra = "overdue=%d fee_due=%d tm=%d data=%d" % (
                len(dd["overdue"]), len(dd["fee_due"]), len(dd["tm_renew"]), len(dd["data_renew"]))
        elif path == "/stats/analysis":
            extra = "score=%d concl=%d" % (d["data"]["overall"], len(d["data"]["conclusions"]))
        T("统计 " + path, okv, extra)

    print("== 战略接口 ==")
    s, d = call("GET", "/strategies")
    n0 = d["data"]["total"]
    T("战略列表", s == 200 and n0 > 0, "total=%d" % n0)
    s, d = call("POST", "/strategies", {"module": "risk", "title": "冒烟测试风险项",
                                        "risk_level": "高", "content": "c", "actions": "a"})
    sid = d.get("data", {}).get("id")
    T("新增战略条目", s == 200 and sid)
    s, d = call("PUT", "/strategies/%s" % sid, {"status": "进行中"})
    T("更新战略条目", s == 200 and d["data"]["status"] == "进行中")
    s, d = call("DELETE", "/strategies/%s" % sid)
    T("删除战略条目", s == 200)
    s, d = call("POST", "/strategy/rebuild", {})
    T("重建智能建议", s == 200 and d["data"]["rebuilt"] > 0, d["data"]["rebuilt"])

    print("== 数据管理 ==")
    s, d = call("GET", "/export")
    okv = s == 200 and len(d["data"]["assets"]) > 0
    T("导出备份", okv, "assets=%d strategies=%d" % (
        len(d["data"]["assets"]), len(d["data"]["strategies"])))
    backup = d["data"]
    s, d = call("POST", "/import", {"data": backup})
    T("导入恢复", s == 200 and d["data"]["assets"] == len(backup["assets"]), d.get("data"))

    s, d = call("GET", "/assets")
    T("导入后数据完整", d["data"]["total"] == len(backup["assets"]), d["data"]["total"])

    s, d = call("POST", "/reset", {"mode": "demo"})
    T("恢复演示数据", s == 200 and d["data"]["assets"] == 29, d.get("data"))

    s, d = call("GET", "/assets/99999")
    T("不存在的资源返回 404", s == 404)

    print("\n== 汇总 ==")
    print("通过 %d / %d" % (sum(1 for x in results if x), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
