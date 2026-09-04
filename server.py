# -*- coding: utf-8 -*-
"""企业知识产权管理系统 - HTTP 服务入口（仅使用 Python 标准库）

启动：python server.py [port]
数据：data/ipms.db（SQLite，持久化，刷新与重启后数据仍在）
"""
import os
import sys
import json
import mimetypes
import socket
import threading
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

import db
import api

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# 端口：命令行位置参数 > 环境变量 PORT（云端部署平台注入）> 默认 8770
_positional = [a for a in sys.argv[1:] if not a.startswith("-")]
PORT = int(_positional[0]) if _positional else int(os.environ.get("PORT") or 8770)
# 绑定地址：平台注入 PORT 时按部署环境处理监听全部网卡，本地运行默认仅回环
HOST = os.environ.get("IPMS_HOST") or ("0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")

MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
        ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "IPMS/1.0"

    # ---------------- 工具 ----------------
    def log_message(self, fmt, *args):
        # 精简日志，避免刷屏
        if "/api/" in (args[0] if args else ""):
            sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, code, body=b"", ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _serve_static(self, path):
        if path == "/" or path == "":
            path = "/index.html"
        rel = unquote(path).lstrip("/")
        full = os.path.normpath(os.path.join(STATIC_DIR, rel))
        if not full.startswith(STATIC_DIR) or not os.path.isfile(full):
            return self._send(404, {"ok": False, "error": "not found"}, "application/json; charset=utf-8")
        ext = os.path.splitext(full)[1].lower()
        ctype = MIME.get(ext) or mimetypes.types_map.get(ext) or "application/octet-stream"
        with open(full, "rb") as f:
            data = f.read()
        self._send(200, data, ctype)

    # ---------------- 路由 ----------------
    def do_OPTIONS(self):
        self._send(204)

    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, {k: v[0] for k, v in parse_qs(u.query).items()}
        if not p.startswith("/api/"):
            return self._serve_static(p)

        conn = db.connect()
        try:
            if p == "/api/company":
                r = api.get_company(conn)
            elif p == "/api/assets":
                r = api.list_assets(conn, q)
            elif p.startswith("/api/assets/") and p.endswith("/logs"):
                r = api.get_asset(conn, int(p.split("/")[3]))
            elif p.startswith("/api/assets/") and p.endswith("/fees"):
                r = api.get_asset(conn, int(p.split("/")[3]))
            elif p.startswith("/api/assets/"):
                r = api.get_asset(conn, int(p.split("/")[3]))
            elif p == "/api/stats/overview":
                r = api.stats_overview(conn, q)
            elif p == "/api/stats/trend":
                r = api.stats_trend(conn, q)
            elif p == "/api/stats/expiry":
                r = api.stats_expiry(conn, q)
            elif p == "/api/stats/distribution":
                r = api.stats_distribution(conn, q)
            elif p == "/api/stats/analysis":
                r = api.stats_analysis(conn, q)
            elif p == "/api/stats/deep":
                r = api.stats_deep(conn, q)
            elif p == "/api/calendar":
                r = api.calendar(conn, q)
            elif p == "/api/export/csv":
                r = api.export_csv(conn, q)
            elif p == "/api/export/xls":
                r = api.export_xls(conn, q)
            elif p == "/api/template/csv":
                r = api.template_csv(conn, q)
            elif p == "/api/strategies":
                r = api.list_strategies(conn, q)
            elif p == "/api/meta":
                r = api.get_meta(conn, q)
            elif p == "/api/export":
                data = api.export_data(conn)
                return self._send(200, {"ok": True, "data": data},
                                  "application/json; charset=utf-8",
                                  {"Content-Disposition": 'attachment; filename="ipms-backup.json"'})
            elif p == "/api/health":
                r = api.ok({"status": "up", "db": db.DB_PATH})
            else:
                r = api.err("未知接口 %s" % p, 404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            r = api.err("服务端异常：%s" % e, 500)
        finally:
            conn.close()
        code = 200 if r.get("ok") else r.get("code", 400)
        self._send(code, r)

    def do_POST(self):
        u = urlparse(self.path)
        p = u.path
        body = self._body()
        if not p.startswith("/api/"):
            return self._send(404, api.err("not found", 404))
        conn = db.connect()
        try:
            if p == "/api/assets":
                r = api.create_asset(conn, body)
            elif p.startswith("/api/assets/") and p.endswith("/logs"):
                r = api.add_log(conn, int(p.split("/")[3]), body)
            elif p.startswith("/api/assets/") and p.endswith("/fees"):
                r = api.add_fee(conn, int(p.split("/")[3]), body)
            elif p == "/api/strategies":
                r = api.create_strategy(conn, body)
            elif p == "/api/strategy/rebuild":
                r = api.rebuild_strategy(conn, body)
            elif p == "/api/import":
                r = api.import_data(conn, body.get("data") if "data" in body else body)
            elif p == "/api/import/csv":
                r = api.import_csv(conn, body)
            elif p == "/api/reset":
                r = api.reset_data(conn, body)
            else:
                r = api.err("未知接口 %s" % p, 404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            r = api.err("服务端异常：%s" % e, 500)
        finally:
            conn.close()
        code = 200 if r.get("ok") else r.get("code", 400)
        self._send(code, r)

    def do_PUT(self):
        u = urlparse(self.path)
        p = u.path
        body = self._body()
        conn = db.connect()
        try:
            if p == "/api/company":
                r = api.update_company(conn, body)
            elif p.startswith("/api/assets/"):
                r = api.update_asset(conn, int(p.split("/")[3]), body)
            elif p.startswith("/api/strategies/"):
                r = api.update_strategy(conn, int(p.split("/")[3]), body)
            elif p.startswith("/api/fees/"):
                r = api.update_fee(conn, int(p.split("/")[3]), body)
            else:
                r = api.err("未知接口 %s" % p, 404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            r = api.err("服务端异常：%s" % e, 500)
        finally:
            conn.close()
        code = 200 if r.get("ok") else r.get("code", 400)
        self._send(code, r)

    def do_DELETE(self):
        u = urlparse(self.path)
        p = u.path
        conn = db.connect()
        try:
            if p.startswith("/api/assets/"):
                r = api.delete_asset(conn, int(p.split("/")[3]))
            elif p.startswith("/api/strategies/"):
                r = api.delete_strategy(conn, int(p.split("/")[3]))
            elif p.startswith("/api/logs/"):
                r = api.delete_log(conn, int(p.split("/")[3]))
            elif p.startswith("/api/fees/"):
                r = api.delete_fee(conn, int(p.split("/")[3]))
            else:
                r = api.err("未知接口 %s" % p, 404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            r = api.err("服务端异常：%s" % e, 500)
        finally:
            conn.close()
        code = 200 if r.get("ok") else r.get("code", 400)
        self._send(code, r)


class _LoopbackV6Server(ThreadingHTTPServer):
    """仅监听 ::1 的 IPv6 服务，与 IPv4 回环并存，不对外网暴露"""

    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        super().server_bind()


def main():
    db.init_db()
    strategy_needed = False
    conn = db.connect()
    try:
        n = conn.execute("SELECT COUNT(*) c FROM strategies WHERE source='auto'").fetchone()["c"]
        strategy_needed = n == 0
    finally:
        conn.close()
    if strategy_needed:
        import strategy
        strategy.rebuild()
    if HOST in ("127.0.0.1", "localhost", "::1"):
        srvs = [ThreadingHTTPServer(("127.0.0.1", PORT), Handler)]
        # Windows 上 localhost 优先解析到 ::1，只监听 IPv4 会导致 localhost 打不开
        try:
            srvs.append(_LoopbackV6Server(("::1", PORT, 0, 0), Handler))
        except OSError:
            pass
    else:
        srvs = [ThreadingHTTPServer((HOST, PORT), Handler)]
    url = "http://127.0.0.1:%d/" % PORT
    print("=" * 58)
    print("  Enterprise IP Management System")
    print("  Host  : %s" % HOST)
    print("  URL   : %s" % (url if HOST in ("127.0.0.1", "::1") else "http://%s:%d/" % (HOST, PORT)))
    if HOST == "127.0.0.1":
        print("        : http://localhost:%d/" % PORT)
    print("  DB    : %s" % db.DB_PATH)
    print("  Stop  : Ctrl+C")
    print("=" * 58)
    sys.stdout.flush()
    if "--no-browser" not in sys.argv and HOST in ("127.0.0.1", "::1"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    for s in srvs[1:]:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        srvs[0].serve_forever()
    except KeyboardInterrupt:
        print("\nBye.")
        for s in srvs:
            s.shutdown()


if __name__ == "__main__":
    main()
