# -*- coding: utf-8 -*-
"""企业知识产权管理系统 - 数据层（SQLite，标准库实现，零第三方依赖）"""
import os
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_db_path():
    """数据库位置：优先 IPMS_DB 环境变量，其次源码下的 data/，
    只读文件系统时回落到系统临时目录，保证云端部署也能写入"""
    env = os.environ.get("IPMS_DB")
    if env:
        return env
    p = os.path.join(BASE_DIR, "data", "ipms.db")
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "ab"):
            pass
        return p
    except OSError:
        return os.path.join(tempfile.gettempdir(), "ipms.db")


DB_PATH = _resolve_db_path()

# 今日基准：用于演示数据的相对日期计算
TODAY = datetime(2026, 9, 4)


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _d(offset_days=0, base=None):
    return ((base or TODAY) + timedelta(days=offset_days)).strftime("%Y-%m-%d")


SCHEMA = """
CREATE TABLE IF NOT EXISTS company (
  id           INTEGER PRIMARY KEY CHECK(id=1),
  name         TEXT DEFAULT '',
  credit_code  TEXT DEFAULT '',
  industry     TEXT DEFAULT '',
  company_type TEXT DEFAULT '',
  address      TEXT DEFAULT '',
  founded_date TEXT DEFAULT '',
  capital      REAL DEFAULT 0,
  legal_person TEXT DEFAULT '',
  contact      TEXT DEFAULT '',
  phone        TEXT DEFAULT '',
  email        TEXT DEFAULT '',
  website      TEXT DEFAULT '',
  ip_dept      TEXT DEFAULT '',
  ip_manager   TEXT DEFAULT '',
  intro        TEXT DEFAULT '',
  updated_at   TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS assets (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  category      TEXT NOT NULL,
  sub_type      TEXT DEFAULT '',
  name          TEXT NOT NULL,
  app_no        TEXT DEFAULT '',
  app_date      TEXT DEFAULT '',
  grant_no      TEXT DEFAULT '',
  grant_date    TEXT DEFAULT '',
  applicant     TEXT DEFAULT '',
  creators      TEXT DEFAULT '',
  agency        TEXT DEFAULT '',
  class_no      TEXT DEFAULT '',
  tech_field    TEXT DEFAULT '',
  department    TEXT DEFAULT '',
  status        TEXT DEFAULT '申请中',
  status_date   TEXT DEFAULT '',
  fee_year      INTEGER DEFAULT 0,
  fee_paid      INTEGER DEFAULT 0,
  next_fee_date TEXT DEFAULT '',
  protect_start TEXT DEFAULT '',
  protect_end   TEXT DEFAULT '',
  scope_text    TEXT DEFAULT '',
  scope_items   TEXT DEFAULT '[]',
  region        TEXT DEFAULT '国内',
  key_points    TEXT DEFAULT '',
  rival_ref     TEXT DEFAULT '',
  remark        TEXT DEFAULT '',
  created_at    TEXT DEFAULT '',
  updated_at    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS status_logs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_id    INTEGER NOT NULL,
  change_date TEXT DEFAULT '',
  old_status  TEXT DEFAULT '',
  new_status  TEXT DEFAULT '',
  note        TEXT DEFAULT '',
  created_at  TEXT DEFAULT '',
  FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS fee_records (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_id   INTEGER NOT NULL,
  year       INTEGER DEFAULT 0,
  amount     REAL DEFAULT 0,
  due_date   TEXT DEFAULT '',
  paid_date  TEXT DEFAULT '',
  paid       INTEGER DEFAULT 0,
  note       TEXT DEFAULT '',
  created_at TEXT DEFAULT '',
  FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS strategies (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  module     TEXT DEFAULT 'risk',
  title      TEXT DEFAULT '',
  category   TEXT DEFAULT '',
  risk_level TEXT DEFAULT '中',
  content    TEXT DEFAULT '',
  actions    TEXT DEFAULT '',
  owner      TEXT DEFAULT '',
  deadline   TEXT DEFAULT '',
  source     TEXT DEFAULT 'manual',
  status     TEXT DEFAULT '待启动',
  created_at TEXT DEFAULT '',
  updated_at TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category);
CREATE INDEX IF NOT EXISTS idx_assets_status   ON assets(status);
CREATE INDEX IF NOT EXISTS idx_logs_asset      ON status_logs(asset_id);
CREATE INDEX IF NOT EXISTS idx_fees_asset      ON fee_records(asset_id);
"""


def init_db():
    try:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    except OSError:
        pass          # 只读文件系统下 DB_PATH 已回落到临时目录，目录必然存在
    conn = connect()
    conn.executescript(SCHEMA)
    conn.commit()
    n = conn.execute("SELECT COUNT(*) c FROM assets").fetchone()["c"]
    if n == 0:
        _seed_company(conn)
        _seed_assets(conn)
        _seed_strategies(conn)
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------
# 演示数据
# --------------------------------------------------------------------------
COMPANY = dict(
    id=1,
    name="衢州量智科技有限公司",
    credit_code="91330800MA2DGH7X4K",
    industry="工业物联网 / 智能装备制造",
    company_type="民营企业",
    address="浙江省衢州市柯城区世纪大道 686 号智慧产业园 A 座 12 层",
    founded_date="2016-04-18",
    capital=5000.0,
    legal_person="顾晓",
    contact="方晓汾",
    phone="0570-8888 6688",
    email="ip@liangzhi-tech.com",
    website="www.liangzhi-tech.com",
    ip_dept="知识产权部",
    ip_manager="方晓汾",
    intro=(
        "衢州量智科技有限公司成立于 2016 年，是一家专注于工业物联网感知层设备、"
        "污水处理智能控制装备与电力标准数字化服务的高新技术企业。"
        "公司围绕电动吸盘执行机构、边缘计算网关、水质在线监测与工艺优化算法四大产品线，"
        "累计研发投入占营业收入比重连续五年超过 8%。"
        "公司已通过知识产权贯标认证（GB/T 29490），设有独立知识产权部，"
        "实行\"研发立项—专利检索—布局申报—维护运营\"全流程管理，"
        "并逐步将核心工艺数据集申请数据知识产权登记，探索数据资产入表路径。"
    ),
)


def _seed_company(conn):
    c = dict(COMPANY)
    c["updated_at"] = _d()
    cols = ",".join(c.keys())
    ph = ",".join("?" * len(c))
    conn.execute(f"INSERT INTO company ({cols}) VALUES ({ph})", list(c.values()))


# 演示数据：每条 = 基本信息 / 法律状态 / 保护范围 三板块
ASSETS = [
    # ---------------- 发明专利 ----------------
    dict(category="专利", sub_type="发明专利",
         name="一种基于电动吸盘负压反馈的自适应抓取控制方法",
         app_no="202010356782.1", app_date="2020-04-22",
         grant_no="ZL202010356782.1", grant_date="2022-08-16",
         applicant="衢州量智科技有限公司", creators="方晓汾; 廿二; 王建国",
         agency="杭州中科专利代理事务所", class_no="B25J 15/06 (2006.01)",
         tech_field="智能装备 / 末端执行器", department="研发中心",
         status="有效", status_date="2022-08-16",
         fee_year=6, fee_paid=1, next_fee_date="2027-04-22",
         protect_start="2020-04-22", protect_end="2040-04-21",
         scope_text=("权利要求 1：一种自适应抓取控制方法，其特征在于，通过负压传感器实时采集吸盘腔体内压力值 P，"
                     "控制器按 ΔP/Δt 判断工件贴合状态，当 ΔP/Δt 超过第一阈值时判定为泄漏并自动提升真空泵占空比；"
                     "权利要求 3-5 限定多级真空发生器的并联切换逻辑；权利要求 7 限定基于工件材质库的负压上限自适应整定。"),
         scope_items=["独立权利要求 1 项，从属权利要求 11 项", "说明书 23 页，附图 7 幅",
                      "核心保护点：负压变化率判漏 + 真空泵占空比闭环调节"],
         region="国内", key_points="负压变化率判漏算法；真空泵占空比闭环；材质库自适应整定",
         rival_ref="德国 SCHUNK、日本 SMC 同类自适应抓取专利族",
         remark="核心基础专利，已质押给衢州农商行用于科技贷"),

    dict(category="专利", sub_type="发明专利",
         name="一种污水处理曝气系统的溶解氧前馈-反馈复合控制方法",
         app_no="202110689234.5", app_date="2021-06-09",
         grant_no="ZL202110689234.5", grant_date="2023-11-21",
         applicant="衢州量智科技有限公司", creators="方晓汾; 李默; 陈玉兰",
         agency="北京工信知识产权代理有限公司", class_no="C02F 3/12 (2023.01); G05B 13/04 (2006.01)",
         tech_field="污水处理 / 过程控制", department="水务事业部",
         status="有效", status_date="2023-11-21",
         fee_year=5, fee_paid=1, next_fee_date="2027-06-09",
         protect_start="2021-06-09", protect_end="2041-06-08",
         scope_text=("权利要求 1：以进水流量 Q 与进水 COD 浓度作为前馈量，以好氧末端溶解氧 DO 作为反馈量，"
                     "构建鼓风机频率的串级控制回路；权利要求 4 限定污泥龄 SRT 与 DO 设定值的耦合修正；"
                     "权利要求 8 限定基于历史数据的曝气能耗寻优目标函数。"),
         scope_items=["独立权利要求 1 项，从属权利要求 9 项", "说明书 18 页，附图 5 幅",
                      "核心保护点：进水负荷前馈 + 末端 DO 反馈的串级曝气控制"],
         region="国内", key_points="进水负荷前馈；串级曝气；能耗寻优目标函数",
         rival_ref="北控水务、首创环保相关曝气节能专利",
         remark="已在衢州城东污水厂 10 万吨/日项目中实施"),

    dict(category="专利", sub_type="发明专利",
         name="面向电力标准文档的条款级知识图谱构建与数字化映射方法",
         app_no="202310458912.7", app_date="2023-05-18",
         grant_no="", grant_date="",
         applicant="衢州量智科技有限公司", creators="顾晓; 方晓汾; 孙一鸣",
         agency="上海专利商标事务所有限公司", class_no="G06F 16/36 (2019.01); G06N 5/022 (2023.01)",
         tech_field="电力信息化 / 知识工程", department="数字化研究院",
         status="审查中", status_date="2025-03-12",
         fee_year=0, fee_paid=0, next_fee_date="",
         protect_start="", protect_end="",
         scope_text=("权利要求 1：对电力标准文本进行条款切分，抽取术语实体、指标实体与约束关系，"
                     "构建以条款为节点的知识图谱；权利要求 5 限定标准间引用关系的版本对齐方法；"
                     "权利要求 9 限定图谱到结构化数据表的映射规则自动生成。"),
         scope_items=["提交权利要求 12 项", "说明书 26 页，附图 9 幅",
                      "核心保护点：条款级知识抽取 + 标准引用的版本对齐"],
         region="国内", key_points="条款级切分；术语/指标实体抽取；标准版本对齐",
         rival_ref="国网电科院、南瑞集团标准数字化相关申请",
         remark="一通已答复，等待二通；建议同步布局 PCT"),

    dict(category="专利", sub_type="发明专利",
         name="一种边缘计算网关的多协议自适应接入与数据缓存方法",
         app_no="201910783451.2", app_date="2019-08-27",
         grant_no="ZL201910783451.2", grant_date="2021-12-03",
         applicant="衢州量智科技有限公司", creators="廿二; 周立",
         agency="杭州中科专利代理事务所", class_no="H04L 12/28 (2006.01); H04L 69/08 (2022.01)",
         tech_field="工业物联网 / 边缘计算", department="研发中心",
         status="有效", status_date="2021-12-03",
         fee_year=7, fee_paid=0, next_fee_date=_d(21),
         protect_start="2019-08-27", protect_end="2039-08-26",
         scope_text=("权利要求 1：网关自动识别 Modbus/Profinet/OPC UA 等协议类型并加载对应驱动；"
                     "权利要求 4 限定断网期间的本地环形缓存与重连补传机制；"
                     "权利要求 6 限定按数据优先级分级上传策略。"),
         scope_items=["独立权利要求 1 项，从属权利要求 10 项", "说明书 20 页，附图 6 幅",
                      "核心保护点：协议自动识别 + 断网环形缓存补传"],
         region="国内", key_points="多协议自适应；断网缓存补传；分级上传",
         rival_ref="华为、研华科技边缘网关专利",
         remark="第 7 年年费即将到期，需在缴费期内缴纳"),

    dict(category="专利", sub_type="发明专利",
         name="一种基于机器视觉的水质浊度在线反演方法",
         app_no="202210912345.8", app_date="2022-09-15",
         grant_no="", grant_date="",
         applicant="衢州量智科技有限公司", creators="陈玉兰; 王建国",
         agency="北京工信知识产权代理有限公司", class_no="G01N 21/59 (2006.01); G06T 7/00 (2017.01)",
         tech_field="水质监测 / 机器视觉", department="水务事业部",
         status="驳回", status_date="2025-11-20",
         fee_year=0, fee_paid=0, next_fee_date="",
         protect_start="", protect_end="",
         scope_text=("权利要求 1：采集水样透射光图像，提取灰度共生矩阵特征，输入回归模型反演浊度值。"
                     "复审后仍被认为相对于对比文件 1 与对比文件 2 的结合不具备创造性。"),
         scope_items=["原权利要求 8 项", "说明书 15 页，附图 4 幅"],
         region="国内", key_points="灰度共生矩阵特征；浊度回归反演",
         rival_ref="聚光科技、力合科技在线水质分析仪专利",
         remark="已驳回生效，技术要点已转为技术秘密保护，并改走软著登记路线"),

    dict(category="专利", sub_type="发明专利",
         name="一种吸盘阵列的能耗均衡调度方法及系统",
         app_no="202410267189.3", app_date="2024-03-11",
         grant_no="", grant_date="",
         applicant="衢州量智科技有限公司", creators="方晓汾; 廿二",
         agency="杭州中科专利代理事务所", class_no="B25J 15/00 (2006.01); G05B 19/418 (2006.01)",
         tech_field="智能装备 / 能耗优化", department="研发中心",
         status="申请中", status_date="2024-03-11",
         fee_year=0, fee_paid=0, next_fee_date="",
         protect_start="", protect_end="",
         scope_text=("权利要求 1：对吸盘阵列中多个真空发生单元按历史能耗与剩余寿命进行轮询调度；"
                     "权利要求 6 限定阵列分组的负载均衡判据。"),
         scope_items=["提交权利要求 10 项", "说明书 17 页，附图 5 幅"],
         region="国内", key_points="阵列轮询调度；能耗与寿命双目标均衡",
         rival_ref="SCHUNK 吸盘阵列能耗管理专利族",
         remark="等待实质审查请求，需在 2027-03-11 前提实审"),

    # ---------------- 实用新型 ----------------
    dict(category="专利", sub_type="实用新型专利",
         name="一种带缓冲结构的电动真空吸盘",
         app_no="202020456781.9", app_date="2020-03-30",
         grant_no="ZL202020456781.9", grant_date="2021-01-15",
         applicant="衢州量智科技有限公司", creators="廿二; 王建国",
         agency="杭州中科专利代理事务所", class_no="B25J 15/06 (2006.01)",
         tech_field="智能装备 / 末端执行器", department="研发中心",
         status="有效", status_date="2021-01-15",
         fee_year=6, fee_paid=1, next_fee_date="2027-03-30",
         protect_start="2020-03-30", protect_end="2030-03-29",
         scope_text=("权利要求 1：吸盘本体与连接法兰之间设置弹性缓冲套，缓冲套内嵌位移传感器，"
                     "在接触瞬间吸收冲击并输出接触信号；权利要求 3 限定缓冲套的波纹结构与行程限位。"),
         scope_items=["权利要求 8 项", "说明书 11 页，附图 4 幅",
                      "核心保护点：弹性缓冲套 + 内嵌位移传感"],
         region="国内", key_points="波纹缓冲套；接触信号输出；行程限位",
         rival_ref="SMC 缓冲吸盘结构专利", remark="与核心发明专利形成组合保护"),

    dict(category="专利", sub_type="实用新型专利",
         name="一种模块化多通道水质采样预处理装置",
         app_no="202121567890.4", app_date="2021-07-14",
         grant_no="ZL202121567890.4", grant_date="2022-02-18",
         applicant="衢州量智科技有限公司", creators="陈玉兰; 李默",
         agency="北京工信知识产权代理有限公司", class_no="G01N 1/10 (2006.01)",
         tech_field="水质监测 / 采样装置", department="水务事业部",
         status="有效", status_date="2022-02-18",
         fee_year=5, fee_paid=1, next_fee_date="2027-07-14",
         protect_start="2021-07-14", protect_end="2031-07-13",
         scope_text=("权利要求 1：多路采样通道采用快插式滤芯模块，单通道故障可在线更换；"
                     "权利要求 4 限定反冲洗流路与取样计量泵的联动。"),
         scope_items=["权利要求 9 项", "说明书 12 页，附图 6 幅"],
         region="国内", key_points="快插滤芯；在线更换；反冲洗联动",
         rival_ref="力合科技水质采样器结构专利", remark="配套在线监测产品销售"),

    dict(category="专利", sub_type="实用新型专利",
         name="一种工业网关的防尘防水散热壳体",
         app_no="202222345678.1", app_date="2022-11-23",
         grant_no="ZL202222345678.1", grant_date="2023-06-09",
         applicant="衢州量智科技有限公司", creators="周立; 孙一鸣",
         agency="杭州中科专利代理事务所", class_no="H05K 5/02 (2006.01); H05K 7/20 (2006.01)",
         tech_field="工业物联网 / 结构设计", department="研发中心",
         status="有效", status_date="2023-06-09",
         fee_year=4, fee_paid=1, next_fee_date="2026-11-23",
         protect_start="2022-11-23", protect_end="2032-11-22",
         scope_text=("权利要求 1：壳体采用铝合金型材挤压成型，散热鳍片与壳体一体成型，"
                     "接口面设置双层硅胶密封条并达到 IP67 防护等级。"),
         scope_items=["权利要求 7 项", "说明书 9 页，附图 3 幅"],
         region="国内", key_points="一体成型散热鳍片；双层密封 IP67",
         rival_ref="研华、MOXA 工业网关外壳专利", remark="第 4 年年费将于本年度内到期"),

    dict(category="专利", sub_type="实用新型专利",
         name="一种曝气盘可提升式安装支架",
         app_no="201821234567.3", app_date="2018-05-16",
         grant_no="ZL201821234567.3", grant_date="2019-03-22",
         applicant="衢州量智科技有限公司", creators="李默",
         agency="北京工信知识产权代理有限公司", class_no="C02F 3/20 (2006.01)",
         tech_field="污水处理 / 曝气设备", department="水务事业部",
         status="失效", status_date="2024-05-16",
         fee_year=6, fee_paid=0, next_fee_date="",
         protect_start="2018-05-16", protect_end="2028-05-15",
         scope_text=("权利要求 1：曝气盘通过提升杆与池顶支架连接，可在不放空池体的条件下整体提升至水面检修。"),
         scope_items=["权利要求 6 项", "说明书 8 页，附图 4 幅"],
         region="国内", key_points="可提升检修；不放空池体",
         rival_ref="—", remark="因第 6 年年费逾期未缴而终止，产品已迭代不再使用"),

    dict(category="专利", sub_type="实用新型专利",
         name="一种带自诊断功能的电动吸盘控制器",
         app_no="202323456789.2", app_date="2023-12-08",
         grant_no="ZL202323456789.2", grant_date="2024-08-02",
         applicant="衢州量智科技有限公司", creators="方晓汾; 周立",
         agency="杭州中科专利代理事务所", class_no="B25J 19/00 (2006.01)",
         tech_field="智能装备 / 控制器", department="研发中心",
         status="年费滞纳", status_date=_d(-40),
         fee_year=3, fee_paid=0, next_fee_date=_d(-40),
         protect_start="2023-12-08", protect_end="2033-12-07",
         scope_text=("权利要求 1：控制器周期性向吸盘执行单元发送自检指令，比对回采电流与基准值，"
                     "偏差超限时上报故障码并切换备用通道。"),
         scope_items=["权利要求 8 项", "说明书 10 页，附图 3 幅"],
         region="国内", key_points="周期性自检；电流比对；备用通道切换",
         rival_ref="—", remark="已进入年费滞纳期，须在滞纳期内补缴并缴纳滞纳金，否则专利权终止"),

    # ---------------- 外观设计 ----------------
    dict(category="专利", sub_type="外观设计专利",
         name="工业边缘计算网关（LZ-G200）",
         app_no="202130567891.2", app_date="2021-08-25",
         grant_no="ZL202130567891.2", grant_date="2022-03-11",
         applicant="衢州量智科技有限公司", creators="周立",
         agency="杭州中科专利代理事务所", class_no="洛迦诺 14-03",
         tech_field="工业物联网 / 工业设计", department="研发中心",
         status="有效", status_date="2022-03-11",
         fee_year=5, fee_paid=1, next_fee_date="2027-08-25",
         protect_start="2021-08-25", protect_end="2036-08-24",
         scope_text=("本外观设计产品的用途：用于工业现场设备数据采集与协议转换。设计要点：在于产品的整体形状，"
                     "尤其是顶面散热鳍片的等距阵列排布与正面斜切式指示灯带。最能表明设计要点的图片：立体图 1。"),
         scope_items=["图片 7 幅（六面正投影图 + 立体图）", "简要说明 1 页",
                      "设计要点：顶面等距散热鳍片阵列 + 正面斜切指示灯带"],
         region="国内", key_points="散热鳍片阵列造型；斜切指示灯带",
         rival_ref="研华 UNO 系列网关外观", remark="配套 LZ-G200 产品", area_note=""),

    dict(category="专利", sub_type="外观设计专利",
         name="水质在线监测仪（LZ-W100）",
         app_no="202230789123.5", app_date="2022-10-19",
         grant_no="ZL202230789123.5", grant_date="2023-05-16",
         applicant="衢州量智科技有限公司", creators="陈玉兰",
         agency="北京工信知识产权代理有限公司", class_no="洛迦诺 10-05",
         tech_field="水质监测 / 工业设计", department="水务事业部",
         status="有效", status_date="2023-05-16",
         fee_year=4, fee_paid=1, next_fee_date="2026-10-19",
         protect_start="2022-10-19", protect_end="2037-10-18",
         scope_text=("本外观设计产品的用途：用于水质的在线连续监测。设计要点：在于正面上部的大尺寸触控显示区"
                     "与下部进样仓的外凸矩形造型。最能表明设计要点的图片：主视图。"),
         scope_items=["图片 6 幅", "简要说明 1 页", "设计要点：大尺寸触控区 + 外凸进样仓"],
         region="国内", key_points="触控显示区比例；外凸进样仓",
         rival_ref="聚光科技在线监测仪外观", remark="第 4 年年费本年度内到期", area_note=""),

    dict(category="专利", sub_type="外观设计专利",
         name="电动吸盘（LZ-S30 圆形）",
         app_no="202330123456.7", app_date="2023-02-14",
         grant_no="ZL202330123456.7", grant_date="2023-09-01",
         applicant="衢州量智科技有限公司", creators="廿二",
         agency="杭州中科专利代理事务所", class_no="洛迦诺 15-99",
         tech_field="智能装备 / 工业设计", department="研发中心",
         status="许可", status_date="2025-06-01",
         fee_year=3, fee_paid=1, next_fee_date="2027-02-14",
         protect_start="2023-02-14", protect_end="2038-02-13",
         scope_text=("本外观设计产品的用途：用于吸附搬运工件。设计要点：吸盘唇边的三环阶梯状密封唇结构"
                     "与顶盖的八边形轮廓。最能表明设计要点的图片：立体图。"),
         scope_items=["图片 7 幅", "简要说明 1 页", "设计要点：三环阶梯密封唇 + 八边形顶盖"],
         region="国内", key_points="三环阶梯密封唇；八边形顶盖",
         rival_ref="SMC 吸盘外观", remark="已普通许可给衢州某装备企业，年许可费 8 万元", area_note=""),

    # ---------------- 软件著作权 ----------------
    dict(category="著作权", sub_type="软件著作权",
         name="量智污水处理智能曝气控制系统 V3.2",
         app_no="软著登字第 9876543 号", app_date="2022-05-20",
         grant_no="2022SR0654321", grant_date="2022-07-08",
         applicant="衢州量智科技有限公司", creators="衢州量智科技有限公司",
         agency="中国版权保护中心（自行申请）", class_no="著作权分类：应用软件-工业控制",
         tech_field="污水处理 / 工业软件", department="水务事业部",
         status="已登记", status_date="2022-07-08",
         fee_year=0, fee_paid=1, next_fee_date="",
         protect_start="2022-05-20", protect_end="2072-12-31",
         scope_text=("软件由曝气数据采集模块、DO 串级控制模块、能耗统计模块与报警管理模块组成，"
                     "源程序 46,800 行，文档 218 页。首次发表日期 2022-05-20，"
                     "保护期为开发完成之日起 50 年。"),
         scope_items=["源程序前后各 30 页，共 60 页", "用户手册 218 页", "开发完成日期：2022-05-20"],
         region="国内", key_points="DO 串级控制模块；能耗统计模块",
         rival_ref="—", remark="与发明专利 ZL202110689234.5 形成\"专利+软著\"组合保护"),

    dict(category="著作权", sub_type="软件著作权",
         name="量智工业网关边缘计算平台软件 V2.0",
         app_no="软著登字第 11223344 号", app_date="2021-03-15",
         grant_no="2021SR0321456", grant_date="2021-05-27",
         applicant="衢州量智科技有限公司", creators="衢州量智科技有限公司",
         agency="中国版权保护中心（自行申请）", class_no="著作权分类：应用软件-数据采集",
         tech_field="工业物联网 / 边缘软件", department="研发中心",
         status="已登记", status_date="2021-05-27",
         fee_year=0, fee_paid=1, next_fee_date="",
         protect_start="2021-03-15", protect_end="2071-12-31",
         scope_text=("软件实现多协议设备接入、边缘规则计算、本地缓存补传与远程运维，"
                     "源程序 62,300 行。首次发表日期 2021-03-15。"),
         scope_items=["源程序前后各 30 页，共 60 页", "操作手册 186 页", "开发完成日期：2021-03-15"],
         region="国内", key_points="多协议接入；边缘规则引擎",
         rival_ref="—", remark="已用于全部网关产品出厂预装"),

    dict(category="著作权", sub_type="软件著作权",
         name="量智电力标准数字化图谱管理平台 V1.0",
         app_no="软著登字第 13579246 号", app_date="2024-09-10",
         grant_no="2024SR1287654", grant_date="2024-11-05",
         applicant="衢州量智科技有限公司", creators="衢州量智科技有限公司",
         agency="浙江省版权协会代办", class_no="著作权分类：应用软件-信息管理",
         tech_field="电力信息化 / 知识工程", department="数字化研究院",
         status="已登记", status_date="2024-11-05",
         fee_year=0, fee_paid=1, next_fee_date="",
         protect_start="2024-09-10", protect_end="2074-12-31",
         scope_text=("软件包含标准文档解析、条款图谱构建、版本比对与合规检查四个功能模块，"
                     "源程序 38,500 行。首次发表日期 2024-09-10。"),
         scope_items=["源程序前后各 30 页，共 60 页", "设计说明书 152 页", "开发完成日期：2024-09-10"],
         region="国内", key_points="条款图谱构建；标准版本比对",
         rival_ref="—", remark="支撑在审发明专利 202310458912.7 的商业化落地"),

    dict(category="著作权", sub_type="软件著作权",
         name="量智电动吸盘阵列调度管理软件 V1.5",
         app_no="软著登字第 14681357 号", app_date="2025-04-08",
         grant_no="2025SR0456789", grant_date="2025-06-19",
         applicant="衢州量智科技有限公司", creators="衢州量智科技有限公司",
         agency="浙江省版权协会代办", class_no="著作权分类：应用软件-嵌入式软件",
         tech_field="智能装备 / 控制软件", department="研发中心",
         status="已登记", status_date="2025-06-19",
         fee_year=0, fee_paid=1, next_fee_date="",
         protect_start="2025-04-08", protect_end="2075-12-31",
         scope_text=("软件实现吸盘阵列分组管理、能耗均衡轮询调度、寿命预测与故障自诊断，"
                     "源程序 27,400 行。首次发表日期 2025-04-08。"),
         scope_items=["源程序前后各 30 页，共 60 页", "用户手册 96 页", "开发完成日期：2025-04-08"],
         region="国内", key_points="分组轮询调度；寿命预测",
         rival_ref="—", remark="配合在申发明专利 202410267189.3"),

    dict(category="著作权", sub_type="软件著作权",
         name="量智水质数据可视化分析平台 V2.1",
         app_no="软著登字第 15892468 号", app_date="2026-02-26",
         grant_no="2026SR0112233", grant_date="2026-04-15",
         applicant="衢州量智科技有限公司", creators="衢州量智科技有限公司",
         agency="浙江省版权协会代办", class_no="著作权分类：应用软件-数据分析",
         tech_field="水质监测 / 数据可视化", department="水务事业部",
         status="已登记", status_date="2026-04-15",
         fee_year=0, fee_paid=1, next_fee_date="",
         protect_start="2026-02-26", protect_end="2076-12-31",
         scope_text=("软件提供多源水质数据接入、时序可视化、超标预警与报表导出，"
                     "源程序 33,900 行。首次发表日期 2026-02-26。"),
         scope_items=["源程序前后各 30 页，共 60 页", "用户手册 124 页", "开发完成日期：2026-02-26"],
         region="国内", key_points="时序可视化；超标预警",
         rival_ref="—", remark="本年度新增登记，支撑数据产品登记的数据来源说明"),

    dict(category="著作权", sub_type="作品著作权",
         name="《量智工业互联网产品宣传图册》美术作品",
         app_no="浙作登字-2023-F-00012345", app_date="2023-04-11",
         grant_no="浙作登字-2023-F-00012345", grant_date="2023-05-06",
         applicant="衢州量智科技有限公司", creators="衢州量智科技有限公司（法人作品）",
         agency="浙江省版权协会代办", class_no="著作权分类：美术作品",
         tech_field="品牌宣传", department="市场部",
         status="已登记", status_date="2023-05-06",
         fee_year=0, fee_paid=1, next_fee_date="",
         protect_start="2023-04-11", protect_end="2073-12-31",
         scope_text=("作品为 32 页产品宣传图册，含原创产品摄影、版式设计与图形元素，"
                     "由公司市场部委托设计并于 2023-04-11 首次发表，著作权归属公司法人作品。"),
         scope_items=["作品样本 32 页", "作品说明书 1 份", "创作完成日期：2023-03-28"],
         region="国内", key_points="原创版式设计；产品摄影作品",
         rival_ref="—", remark="用于展会与投标文件，防范宣传物料被抄袭"),

    dict(category="著作权", sub_type="作品著作权",
         name="《污水处理工艺三维示意动画》视听作品",
         app_no="浙作登字-2024-I-00067890", app_date="2024-06-20",
         grant_no="浙作登字-2024-I-00067890", grant_date="2024-07-18",
         applicant="衢州量智科技有限公司", creators="方晓汾; 市场部",
         agency="浙江省版权协会代办", class_no="著作权分类：视听作品",
         tech_field="品牌宣传 / 技术培训", department="市场部",
         status="已登记", status_date="2024-07-18",
         fee_year=0, fee_paid=1, next_fee_date="",
         protect_start="2024-06-20", protect_end="2074-12-31",
         scope_text=("作品为时长 6 分 20 秒的三维工艺演示动画，用于客户培训与展会播放，"
                     "含原创脚本、三维建模与配音。创作完成日期 2024-06-10。"),
         scope_items=["作品光盘 1 份", "作品说明书 1 份", "创作完成日期：2024-06-10"],
         region="国内", key_points="三维工艺演示；原创脚本",
         rival_ref="—", remark="与短视频项目素材联动复用"),

    # ---------------- 商标 ----------------
    dict(category="商标", sub_type="注册商标",
         name="量智（第 9 类）",
         app_no="第 45678901 号", app_date="2020-05-12",
         grant_no="第 45678901 号", grant_date="2021-02-07",
         applicant="衢州量智科技有限公司", creators="—",
         agency="浙江裕阳知识产权代理有限公司", class_no="尼斯分类 第 9 类",
         tech_field="科学仪器 / 工业软件", department="市场部",
         status="有效", status_date="2021-02-07",
         fee_year=0, fee_paid=1, next_fee_date="",
         protect_start="2021-02-07", protect_end="2031-02-06",
         scope_text=("核定使用商品/服务（第 9 类）：数据处理设备；计算机外围设备；"
                     "可下载的计算机应用软件；工业遥控操作用电气设备；测量仪器；传感器；"
                     "电动调节装置；工业用放射设备；电子监控装置；电池。"),
         scope_items=["第 9 类：数据处理设备、计算机外围设备、可下载软件、传感器、测量仪器等 10 项",
                      "商标样式：中文\"量智\"标准字体", "是否防御性储备：否"],
         region="国内", key_points="核心类别；主营商品覆盖完整",
         rival_ref="—", remark="主商标，需在 2030-08-07 至 2031-02-06 期间办理续展"),

    dict(category="商标", sub_type="注册商标",
         name="量智（第 42 类）",
         app_no="第 45678902 号", app_date="2020-05-12",
         grant_no="第 45678902 号", grant_date="2021-03-14",
         applicant="衢州量智科技有限公司", creators="—",
         agency="浙江裕阳知识产权代理有限公司", class_no="尼斯分类 第 42 类",
         tech_field="技术服务 / 软件开发", department="市场部",
         status="有效", status_date="2021-03-14",
         fee_year=0, fee_paid=1, next_fee_date="",
         protect_start="2021-03-14", protect_end="2031-03-13",
         scope_text=("核定使用商品/服务（第 42 类）：技术研究；工业品外观设计；"
                     "计算机软件设计；计算机编程；计算机系统分析；平台即服务（PaaS）；"
                     "云计算服务；数据处理算法的开发；水质分析服务。"),
         scope_items=["第 42 类：技术研究、软件设计、计算机编程、PaaS、云计算等 9 项",
                      "商标样式：中文\"量智\"标准字体", "是否防御性储备：否"],
         region="国内", key_points="服务类别；覆盖软件与技术服务",
         rival_ref="—", remark="与技术类服务合同、投标文件配套使用"),

    dict(category="商标", sub_type="注册商标",
         name="LIANGZHI 图形商标（第 7 类）",
         app_no="第 51234567 号", app_date="2020-11-03",
         grant_no="第 51234567 号", grant_date="2021-08-21",
         applicant="衢州量智科技有限公司", creators="—",
         agency="浙江裕阳知识产权代理有限公司", class_no="尼斯分类 第 7 类",
         tech_field="机械设备 / 执行器", department="市场部",
         status="有效", status_date="2021-08-21",
         fee_year=0, fee_paid=1, next_fee_date="",
         protect_start="2021-08-21", protect_end="2031-08-20",
         scope_text=("核定使用商品/服务（第 7 类）：工业机器人；机械手；"
                     "真空泵（机器）；气动传送装置；阀门（机器部件）；泵（机器）；"
                     "电动吸盘（机器部件）；包装机械。"),
         scope_items=["第 7 类：工业机器人、机械手、真空泵、电动吸盘等 8 项",
                      "商标样式：图形 + 拼音 LIANGZHI", "是否防御性储备：否"],
         region="国内", key_points="机械类核心；覆盖电动吸盘主产品",
         rival_ref="—", remark="与第 9 类构成商品+服务交叉保护"),

    dict(category="商标", sub_type="注册商标",
         name="量智云（第 35 类）",
         app_no="第 58765432 号", app_date="2021-09-08",
         grant_no="第 58765432 号", grant_date="2022-06-28",
         applicant="衢州量智科技有限公司", creators="—",
         agency="浙江裕阳知识产权代理有限公司", class_no="尼斯分类 第 35 类",
         tech_field="广告销售 / 商业管理", department="市场部",
         status="撤三风险", status_date=_d(-95),
         fee_year=0, fee_paid=1, next_fee_date="",
         protect_start="2022-06-28", protect_end="2032-06-27",
         scope_text=("核定使用商品/服务（第 35 类）：广告；商业管理和组织咨询；"
                     "为零售目的在通讯媒体上展示商品；进出口代理；"
                     "商业数据分析；计算机数据库信息系统化。"),
         scope_items=["第 35 类：广告、商业管理咨询、进出口代理、商业数据分析等 6 项",
                      "商标样式：中文\"量智云\"", "是否防御性储备：是"],
         region="国内", key_points="防御储备；商业数据分析服务",
         rival_ref="—", remark="注册已满三年，第 35 类部分服务未实际使用，存在被提撤三风险，需补充使用证据"),

    dict(category="商标", sub_type="注册商标",
         name="量智水务（第 40 类）",
         app_no="第 62345678 号", app_date="2022-03-17",
         grant_no="", grant_date="",  # 部分驳回，处于驳回复审阶段，尚未核准注册
         applicant="衢州量智科技有限公司", creators="—",
         agency="浙江裕阳知识产权代理有限公司", class_no="尼斯分类 第 40 类",
         tech_field="材料处理 / 水处理", department="市场部",
         status="申请中", status_date="2022-03-17",
         fee_year=0, fee_paid=0, next_fee_date="",
         protect_start="", protect_end="",
         scope_text=("申请指定使用服务（第 40 类）：水处理；污水净化处理；"
                     "空气净化；废物处理（变形）；金属处理；定制材料装配（替他人）。"
                     "目前处于驳回复审阶段，因与引证商标在第 40 类构成近似被部分驳回。"),
         scope_items=["第 40 类：水处理、污水净化、废物处理等 6 项（部分驳回）",
                      "商标样式：中文\"量智水务\"", "驳回复审中"],
         region="国内", key_points="水处理服务类别；被部分驳回",
         rival_ref="—", remark="需提交使用证据与共存协议争取复审成功，或调整为第 37 类申请"),

    # ---------------- 数据知识产权 ----------------
    dict(category="数据知识产权", sub_type="数据资源登记",
         name="衢州市污水厂曝气能耗时序数据集",
         app_no="浙数据登字第 2023-0002341 号", app_date="2023-10-25",
         grant_no="浙数据登字第 2023-0002341 号", grant_date="2023-11-30",
         applicant="衢州量智科技有限公司", creators="衢州量智科技有限公司",
         agency="浙江省知识产权研究与服务中心（自行办理）", class_no="数据分类：工业数据-环保",
         tech_field="污水处理 / 工业数据", department="水务事业部",
         status="有效", status_date="2023-11-30",
         fee_year=0, fee_paid=1, next_fee_date="",
         protect_start="2023-11-30", protect_end="2025-11-29",
         scope_text=("数据范围：衢州城东污水处理厂 2021-01 至 2023-09 期间，"
                     "鼓风机运行频率、溶解氧、进水 COD 与氨氮、出水水质、分时电价共 6 类字段，"
                     "数据条目 1,268 万条，数据规模 4.2 GB，更新频率日更。"
                     "登记内容：数据来源为自有 SCADA 系统采集，经脱敏与清洗，无个人信息。"),
         scope_items=["数据字段：时间戳、鼓风机频率、DO、进水 COD、进水氨氮、出水 COD、分时电价",
                      "数据量：1,268 万条 / 4.2 GB", "数据来源：自有 SCADA 系统（脱敏清洗）",
                      "样例数据 200 条已存证"],
         region="国内", key_points="能耗-水质耦合时序数据；脱敏清洗规则",
         rival_ref="—", remark="登记有效期 2 年，已于 2025-11-29 到期，需办理续展"),

    dict(category="数据知识产权", sub_type="数据资源登记",
         name="电动吸盘负压工况与故障样本数据集",
         app_no="浙数据登字第 2024-0008892 号", app_date="2024-08-14",
         grant_no="浙数据登字第 2024-0008892 号", grant_date="2024-09-20",
         applicant="衢州量智科技有限公司", creators="衢州量智科技有限公司",
         agency="浙江省知识产权研究与服务中心（自行办理）", class_no="数据分类：工业数据-装备制造",
         tech_field="智能装备 / 工业数据", department="研发中心",
         status="有效", status_date="2024-09-20",
         fee_year=0, fee_paid=1, next_fee_date="",
         protect_start="2024-09-20", protect_end="2026-09-19",
         scope_text=("数据范围：LZ-S 系列吸盘在 8 类典型工件上的负压曲线、贴合判定结果、"
                     "泄漏与打滑故障样本，采样频率 100 Hz，样本数 3.6 万组，数据规模 1.8 GB。"
                     "登记内容：数据来源为自有试验台与客户现场回传（已获授权），已完成匿名化处理。"),
         scope_items=["数据字段：工件类型、负压时序曲线、贴合判定标签、故障类型标签、环境温湿度",
                      "数据量：3.6 万组 / 1.8 GB", "数据来源：自有试验台 + 客户现场（已授权匿名化）",
                      "样例数据 200 条已存证"],
         region="国内", key_points="负压曲线样本；贴合判定的标注规则",
         rival_ref="—", remark="有效期 15 天内到期，须在 2026-09-19 前办理续展"),

    dict(category="数据知识产权", sub_type="数据产品登记",
         name="污水厂曝气优化能耗指数数据产品",
         app_no="浙数据产登字第 2025-0001123 号", app_date="2025-11-06",
         grant_no="浙数据产登字第 2025-0001123 号", grant_date="2025-12-12",
         applicant="衢州量智科技有限公司", creators="衢州量智科技有限公司",
         agency="浙江省知识产权研究与服务中心（自行办理）", class_no="数据分类：数据产品-环保服务",
         tech_field="污水处理 / 数据服务", department="数字化研究院",
         status="有效", status_date="2025-12-12",
         fee_year=0, fee_paid=1, next_fee_date="",
         protect_start="2025-12-12", protect_end="2027-12-11",
         scope_text=("数据产品内容：基于污水厂运行数据计算的\"曝气能耗指数\"，"
                     "按日/月输出能耗基准值、偏离度与节能潜力区间，供污水厂运营方对标使用。"
                     "算法规则：以同规模、同工艺污水厂分组，采用分位数回归构建能耗基准。"),
         scope_items=["输出字段：日期、能耗基准值、实际能耗、偏离度、节能潜力区间",
                      "算法规则：分位数回归 + 同工艺分组对标", "交付方式：API 接口 / 月度报告"],
         region="国内", key_points="能耗指数算法规则；分位数回归基准模型",
         rival_ref="—", remark="已作为数据资产入表试点，对应无形资产账面值 86 万元"),
]

# 状态变更记录（按资产名称索引，仅演示关键的几条）
STATUS_LOGS = {
    "一种带自诊断功能的电动吸盘控制器": [
        ("2023-12-08", "", "申请中", "提交实用新型专利申请"),
        ("2024-08-02", "申请中", "已授权", "授权公告，证书号 ZL202323456789.2"),
        (_d(-40), "已授权", "年费滞纳", "第 3 年年费逾期，进入 6 个月滞纳期"),
    ],
    "一种工业网关的防尘防水散热壳体": [
        ("2022-11-23", "", "申请中", "提交实用新型专利申请"),
        ("2023-06-09", "申请中", "已授权", "授权公告"),
        ("2025-11-23", "已授权", "有效", "第 3 年年费已缴纳"),
    ],
    "一种曝气盘可提升式安装支架": [
        ("2018-05-16", "", "申请中", "提交实用新型专利申请"),
        ("2019-03-22", "申请中", "已授权", "授权公告"),
        ("2024-05-16", "已授权", "失效", "第 6 年年费逾期未缴，专利权终止"),
    ],
    "面向电力标准文档的条款级知识图谱构建与数字化映射方法": [
        ("2023-05-18", "", "申请中", "提交发明专利申请"),
        ("2024-09-25", "申请中", "审查中", "进入实质审查程序"),
        ("2025-03-12", "审查中", "审查中", "发出第一次审查意见通知书，已提交答复"),
    ],
    "一种基于机器视觉的水质浊度在线反演方法": [
        ("2022-09-15", "", "申请中", "提交发明专利申请"),
        ("2023-11-08", "申请中", "审查中", "进入实质审查"),
        ("2025-11-20", "审查中", "驳回", "驳回决定生效，技术要点转技术秘密保护"),
    ],
    "一种基于电动吸盘负压反馈的自适应抓取控制方法": [
        ("2020-04-22", "", "申请中", "提交发明专利申请"),
        ("2021-07-30", "申请中", "审查中", "进入实质审查"),
        ("2022-08-16", "审查中", "已授权", "授权公告，证书号 ZL202010356782.1"),
        ("2024-03-05", "已授权", "质押", "质押给衢州农商行，担保科技贷 600 万元"),
    ],
    "电动吸盘（LZ-S30 圆形）": [
        ("2023-02-14", "", "申请中", "提交外观设计申请"),
        ("2023-09-01", "申请中", "已授权", "授权公告"),
        ("2025-06-01", "已授权", "许可", "普通许可衢州某装备企业，年许可费 8 万元"),
    ],
    "量智云（第 35 类）": [
        ("2021-09-08", "", "申请中", "提交商标注册申请"),
        ("2022-06-28", "申请中", "已注册", "核准注册，专用权期限至 2032-06-27"),
        (_d(-95), "已注册", "撤三风险", "监测到同行检索记录，第 35 类部分服务使用证据不足"),
    ],
    "量智水务（第 40 类）": [
        ("2022-03-17", "", "申请中", "提交商标注册申请"),
        ("2023-05-30", "申请中", "审查中", "部分驳回，进入驳回复审程序"),
    ],
}

# 年费缴纳记录（按资产名称索引）
FEE_RECORDS = {
    "一种基于电动吸盘负压反馈的自适应抓取控制方法": [
        (4, 1200, "2024-04-22", "2024-03-18", 1, "第 4 年年费"),
        (5, 1200, "2025-04-22", "2025-03-25", 1, "第 5 年年费"),
        (6, 1200, "2026-04-22", "2026-03-20", 1, "第 6 年年费"),
    ],
    "一种污水处理曝气系统的溶解氧前馈-反馈复合控制方法": [
        (4, 1200, "2025-06-09", "2025-05-12", 1, "第 4 年年费"),
        (5, 1200, "2026-06-09", "2026-05-18", 1, "第 5 年年费"),
    ],
    "一种边缘计算网关的多协议自适应接入与数据缓存方法": [
        (5, 1200, "2025-08-27", "2025-07-30", 1, "第 5 年年费"),
        (6, 1200, "2026-08-27", "2026-08-05", 1, "第 6 年年费"),
        (7, 2000, _d(21), "", 0, "第 7 年年费，待缴纳（缴费期内）"),
    ],
    "一种带缓冲结构的电动真空吸盘": [
        (5, 600, "2026-03-30", "2026-03-06", 1, "第 5 年年费"),
    ],
    "一种模块化多通道水质采样预处理装置": [
        (4, 600, "2025-07-14", "2025-06-25", 1, "第 4 年年费"),
        (5, 600, "2026-07-14", "2026-06-18", 1, "第 5 年年费"),
    ],
    "一种工业网关的防尘防水散热壳体": [
        (3, 600, "2025-11-23", "2025-10-28", 1, "第 3 年年费"),
        (4, 900, "2026-11-23", "", 0, "第 4 年年费，待缴纳"),
    ],
    "一种曝气盘可提升式安装支架": [
        (5, 600, "2023-05-16", "2023-04-20", 1, "第 5 年年费"),
        (6, 900, "2024-05-16", "", 0, "第 6 年年费逾期未缴，导致专利权终止"),
    ],
    "一种带自诊断功能的电动吸盘控制器": [
        (2, 600, "2025-12-08", "2025-11-15", 1, "第 2 年年费"),
        (3, 600, _d(-40), "", 0, "第 3 年年费逾期，已进入滞纳期"),
    ],
    "工业边缘计算网关（LZ-G200）": [
        (4, 600, "2025-08-25", "2025-07-31", 1, "第 4 年年费"),
        (5, 900, "2026-08-25", "2026-08-02", 1, "第 5 年年费"),
    ],
    "水质在线监测仪（LZ-W100）": [
        (3, 600, "2025-10-19", "2025-09-22", 1, "第 3 年年费"),
        (4, 900, "2026-10-19", "", 0, "第 4 年年费，待缴纳"),
    ],
    "电动吸盘（LZ-S30 圆形）": [
        (2, 600, "2025-02-14", "2025-01-20", 1, "第 2 年年费"),
        (3, 600, "2026-02-14", "2026-01-26", 1, "第 3 年年费"),
    ],
}

STRATEGIES = [
    dict(module="avoid", title="围绕 SCHUNK / SMC 吸盘专利族开展规避设计",
         category="规避设计", risk_level="中",
         content=("德国 SCHUNK 与日本 SMC 在自适应抓取、吸盘阵列能耗管理方向布局密集，"
                  "其独立权利要求多围绕\"基于压力阈值的分级吸附\"展开。"
                  "我方核心专利采用\"负压变化率 ΔP/Δt 判漏 + 真空泵占空比闭环\"的技术路径，"
                  "与竞品的压力阈值判定路径存在实质差异，已形成初步规避。"),
         actions=("1. 对 SCHUNK EP3xxxxxx、SMC JP20xxxxxx 专利族做权利要求逐项比对，出具 FTO 意见；\n"
                  "2. 在吸盘唇边结构、缓冲套波纹参数上继续申请 2-3 件实用新型，形成外围包围；\n"
                  "3. 对无法规避的关键特征，提前洽谈交叉许可。"),
         owner="研发中心 / 方晓汾", deadline=_d(120), source="auto", status="进行中"),

    dict(module="avoid", title="核心控制算法的防御性公开布局",
         category="防御性公开", risk_level="低",
         content=("对暂不申请专利、但需防止竞争对手抢先申请的工艺参数整定方法"
                  "（如材质库负压上限整定的经验取值区间），建议采用防御性公开："
                  "在行业期刊或现有技术数据库公开，使其成为现有技术，阻止他人获得独占权。"),
         actions=("1. 梳理 3-5 项不适合专利保护但具有防御价值的工艺诀窍；\n"
                  "2. 以技术报告形式在行业协会平台公开发布，留存时间戳证据；\n"
                  "3. 同步纳入公司技术秘密清单，签订员工保密协议。"),
         owner="知识产权部 / 方晓汾", deadline=_d(180), source="auto", status="待启动"),

    dict(module="avoid", title="在申发明专利的 PCT 与外围布局",
         category="专利布局", risk_level="中",
         content=("电力标准文档条款级知识图谱方法（202310458912.7）处于审查中，"
                  "该方向为电力标准数字化核心赛道，国网系单位申请量增长迅速。"
                  "建议在 12 个月优先权期限内完成 PCT 国际申请，并围绕图谱映射规则、"
                  "版本对齐、合规检查三个子方向补充 3 件外围申请。"),
         actions=("1. 2026-05-18 前完成 PCT 申请决策与预算审批；\n"
                  "2. 分案申请：图谱到结构化表映射规则、标准引用版本对齐、合规检查规则生成；\n"
                  "3. 与浙江大学合作发表论文，但须先申请专利再公开。"),
         owner="数字化研究院 / 顾晓", deadline=_d(240), source="auto", status="待启动"),

    dict(module="avoid", title="挖掘与申报策略：研发项目专利产出率提升",
         category="挖掘申报", risk_level="低",
         content=("现有专利主要集中于吸盘与曝气控制两个方向，边缘计算网关的软件算法、"
                  "数据产品算法规则尚未形成专利保护。"
                  "建议在研发立项评审节点嵌入专利检索，在样机评审节点嵌入专利挖掘会。"),
         actions=("1. 建立\"立项检索—中期挖掘—结题申报\"三节点制度；\n"
                  "2. 对 2026 年在研的 4 个项目各安排 1 场专利挖掘会；\n"
                  "3. 将专利产出纳入研发人员绩效考核（每项目不少于 1 件发明专利申请）。"),
         owner="知识产权部", deadline=_d(90), source="auto", status="进行中"),

    dict(module="risk", title="年费滞纳风险：实用新型 ZL202323456789.2 专利权可能终止",
         category="年费维持风险", risk_level="高",
         content=("一种带自诊断功能的电动吸盘控制器（ZL202323456789.2）第 3 年年费应缴日已逾期，"
                  "目前处于 6 个月滞纳期内。若在滞纳期届满前仍未补缴年费及滞纳金，"
                  "专利权将自应当缴纳年费期满之日起终止，且该控制器已用于量产产品，"
                  "权利丧失将直接影响产品排他性。"),
         actions=("1. 立即核定滞纳金额（年费 600 元 + 滞纳金 5%/月），7 日内完成补缴；\n"
                  "2. 补缴后索取缴费凭证并核对专利登记簿副本状态；\n"
                  "3. 将全部有效专利的年费纳入系统台账，设置提前 90 天提醒。"),
         owner="知识产权部 / 方晓汾", deadline=_d(30), source="auto", status="进行中"),

    dict(module="risk", title="年费到期提醒：ZL201910783451.2 第 7 年年费待缴纳",
         category="年费维持风险", risk_level="中",
         content=("发明专利 一种边缘计算网关的多协议自适应接入与数据缓存方法（ZL201910783451.2）"
                  "第 7 年年费应缴日为近期，年费标准由 1200 元提高至 2000 元。该专利为网关产品的基础专利，"
                  "须按时缴纳。"),
         actions=("1. 在应缴日前完成第 7 年年费 2000 元的缴纳；\n"
                  "2. 同步核查同族专利年费状态；\n"
                  "3. 将该专利列入年度重点维持清单。"),
         owner="知识产权部", deadline=_d(21), source="auto", status="待启动"),

    dict(module="risk", title="商标撤三风险：量智云（第 35 类）使用证据不足",
         category="商标撤三风险", risk_level="中",
         content=("量智云（第 35 类，注册号第 58765432 号）自 2022-06-28 核准注册已满三年，"
                  "其中\"广告\"\"进出口代理\"等服务未实际开展，缺乏有效使用证据。"
                  "任何单位可依据商标法第四十九条提出撤销申请，一旦被撤，"
                  "公司在广告与数据分析服务上的品牌保护将出现缺口。"),
         actions=("1. 补充近三年在\"商业数据分析\"服务上的合同、发票、宣传物料等使用证据；\n"
                  "2. 对确无使用计划的服务项目，主动提交删减申请降低被撤风险；\n"
                  "3. 在核心的第 9、42 类上补充防御性注册，扩大类似群覆盖。"),
         owner="市场部 / 知识产权部", deadline=_d(60), source="auto", status="待启动"),

    dict(module="risk", title="商标续展提醒：量智（第 9 类 / 第 42 类）",
         category="商标续展风险", risk_level="低",
         content=("量智（第 9 类，第 45678901 号）专用权期限至 2031-02-06，"
                  "量智（第 42 类，第 45678902 号）至 2031-03-13。"
                  "商标续展应在期满前 12 个月内办理，宽展期为期满后 6 个月，"
                  "宽展期内办理需缴纳延迟费。该两件为主商标，必须维持。"),
         actions=("1. 在 2030-02 与 2030-03 分别启动第 9 类、第 42 类续展；\n"
                  "2. 提前核查商标样式与实际使用是否一致，避免被提撤三；\n"
                  "3. 续展前完成商标使用证据归档。"),
         owner="市场部", deadline="2030-02-07", source="auto", status="待启动"),

    dict(module="risk", title="数据知识产权续展风险：2 件登记即将/已经到期",
         category="数据合规风险", risk_level="高",
         content=("电动吸盘负压工况与故障样本数据集（浙数据登字第 2024-0008892 号）有效期至 2026-09-19，"
                  "即将到期；衢州市污水厂曝气能耗时序数据集（浙数据登字第 2023-0002341 号）"
                  "有效期已于 2025-11-29 届满。登记证书失效后，"
                  "在侵权纠纷中将难以依据登记证书主张数据权益，且影响数据资产入表的权属证明。"),
         actions=("1. 在到期前 30 日内提交续展申请，同步更新样例数据；\n"
                  "2. 对已失效的曝气能耗数据集，评估重新登记或补充登记的可行性；\n"
                  "3. 建立数据知识产权有效期台账，纳入年度提醒。"),
         owner="数字化研究院 / 水务事业部", deadline=_d(15), source="auto", status="进行中"),

    dict(module="risk", title="FTO 自由实施分析：曝气控制产品出海",
         category="侵权风险（FTO）", risk_level="中",
         content=("公司曝气控制产品计划出口东南亚，需在目标国开展 FTO 检索。"
                  "北控水务、首创环保在国内已布局多件曝气节能专利，"
                  "另有跨国水处理集团在越南、泰国持有相关专利，"
                  "存在出口产品落入他人保护范围的风险。"),
         actions=("1. 委托当地代理机构对越南、泰国、马来西亚做 FTO 检索；\n"
                  "2. 针对高风险专利做规避设计或无效准备；\n"
                  "3. 出口合同中约定知识产权侵权责任的划分与上限。"),
         owner="水务事业部 / 法务", deadline=_d(150), source="auto", status="待启动"),

    dict(module="risk", title="诉讼与侵权预警：核心专利被跟随风险",
         category="诉讼风险", risk_level="中",
         content=("公司核心专利 ZL202010356782.1 与 ZL202110689234.5 已公开并授权，"
                  "技术方案可通过产品反推获得。行业跟随者可能通过规避设计绕开权利要求，"
                  "或在周边申请改进专利形成反包围。同时该专利已质押，"
                  "若权利不稳定将影响银行授信。"),
         actions=("1. 每季度做一次专利预警检索，监控同 IPC 分类下的新申请；\n"
                  "2. 对疑似跟随申请及时提公众意见或异议；\n"
                  "3. 维持专利有效性，按期缴纳年费，保存研发原始记录。"),
         owner="知识产权部", deadline=_d(75), source="auto", status="待启动"),

    dict(module="risk", title="数据合规风险：客户现场数据的授权链完整性",
         category="数据合规风险", risk_level="中",
         content=("电动吸盘负压工况数据集含客户现场回传数据，"
                  "数据产品\"曝气能耗指数\"涉及多家污水厂运营数据。"
                  "若授权链条不完整（缺少客户数据使用授权、缺少脱敏合规记录），"
                  "将违反数据安全法与个人信息保护法，并影响数据知识产权登记的效力。"),
         actions=("1. 全面梳理数据采集、回传、加工、对外提供各环节的授权文件；\n"
                  "2. 建立数据分类分级清单与脱敏操作留痕机制；\n"
                  "3. 对外提供数据产品前完成数据出境/共享合规审查。"),
         owner="法务 / 数字化研究院", deadline=_d(100), source="auto", status="待启动"),
]


def _seed_assets(conn):
    now = _d()
    for a in ASSETS:
        a = dict(a)
        a.pop("area_note", None)
        a["scope_items"] = json.dumps(a.get("scope_items", []), ensure_ascii=False)
        a.setdefault("fee_year", 0)
        a.setdefault("fee_paid", 0)
        a["created_at"] = now
        a["updated_at"] = now
        cols = ",".join(a.keys())
        ph = ",".join("?" * len(a))
        cur = conn.execute(f"INSERT INTO assets ({cols}) VALUES ({ph})", list(a.values()))
        aid = cur.lastrowid
        for (cd, old, new, note) in STATUS_LOGS.get(a["name"], []):
            conn.execute(
                "INSERT INTO status_logs(asset_id,change_date,old_status,new_status,note,created_at)"
                " VALUES (?,?,?,?,?,?)", (aid, cd, old, new, note, now))
        for (y, amt, due, paid, is_paid, note) in FEE_RECORDS.get(a["name"], []):
            conn.execute(
                "INSERT INTO fee_records(asset_id,year,amount,due_date,paid_date,paid,note,created_at)"
                " VALUES (?,?,?,?,?,?,?,?)", (aid, y, amt, due, paid, is_paid, note, now))


def _seed_strategies(conn):
    now = _d()
    for s in STRATEGIES:
        s = dict(s)
        s["created_at"] = now
        s["updated_at"] = now
        cols = ",".join(s.keys())
        ph = ",".join("?" * len(s))
        conn.execute(f"INSERT INTO strategies ({cols}) VALUES ({ph})", list(s.values()))


if __name__ == "__main__":
    init_db()
    conn = connect()
    print("assets:", conn.execute("SELECT COUNT(*) c FROM assets").fetchone()["c"])
    print("logs:", conn.execute("SELECT COUNT(*) c FROM status_logs").fetchone()["c"])
    print("fees:", conn.execute("SELECT COUNT(*) c FROM fee_records").fetchone()["c"])
    print("strategies:", conn.execute("SELECT COUNT(*) c FROM strategies").fetchone()["c"])
    conn.close()
