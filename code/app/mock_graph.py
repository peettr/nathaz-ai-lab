#!/usr/bin/env python3
"""测试用：本地模拟个人 OneDrive 的几个 Graph 接口（取文件/eTag、If-Match 覆盖、版本列表、恢复版本），外加测试钩子模拟 Liang Hu 在 Word 里改稿。
用法：mock_graph.py <端口> <数据目录> <初始 docx>"""
import json, os, shutil, sys, threading, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

PORT, DIR, INIT = int(sys.argv[1]), sys.argv[2], sys.argv[3]
ITEM = "TESTITEM!101"
os.makedirs(DIR, exist_ok=True)
L = threading.Lock()
VERS = []  # [{id, file, time}]
BUMP = {"on": False}  # 测试：下一次 PUT 之前先插入一个「Liang Hu 刚保存」的版本，制造 eTag 不符


def add_version(data):
    n = len(VERS) + 1
    p = os.path.join(DIR, f"v{n}.docx")
    open(p, "wb").write(data)
    VERS.append({"id": f"{n}.0", "file": p, "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})


add_version(open(INIT, "rb").read())


def etag():
    return f'"{{AAAA-TEST}},{len(VERS)}"'


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def out(self, code, body=b"", ctype="application/json", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def meta(self):
        return {"id": ITEM, "name": "测试稿.docx", "eTag": etag(), "webUrl": f"https://onedrive.live.com/edit.aspx?resid={ITEM}",
                "lastModifiedDateTime": VERS[-1]["time"], "size": os.path.getsize(VERS[-1]["file"])}

    def auth(self):
        if self.headers.get("Authorization") != "Bearer test-token":
            self.out(401, {"error": "unauthorized"})
            return False
        return True

    def do_GET(self):
        u = urlparse(self.path).path
        if not self.auth():
            return
        with L:
            if u == f"/v1.0/me/drive/items/{ITEM}":
                return self.out(200, self.meta())
            if u == f"/v1.0/me/drive/items/{ITEM}/content":
                return self.out(200, open(VERS[-1]["file"], "rb").read(), "application/octet-stream", {"ETag": etag()})
            if u == f"/v1.0/me/drive/items/{ITEM}/versions":
                return self.out(200, {"value": [{"id": v["id"], "lastModifiedDateTime": v["time"]} for v in reversed(VERS)]})
            if u == "/v1.0/me":
                return self.out(200, {"userPrincipalName": "[邮箱]"})
        self.out(404, {"error": "nf"})

    def do_PUT(self):
        u = urlparse(self.path).path
        if not self.auth():
            return
        data = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        with L:
            if u == f"/v1.0/me/drive/items/{ITEM}/content":
                if BUMP["on"]:
                    BUMP["on"] = False
                    add_version(open(VERS[-1]["file"], "rb").read())
                if self.headers.get("If-Match") != etag():
                    return self.out(412, {"error": {"code": "resourceModified", "message": "ETag does not match"}})
                add_version(data)
                return self.out(200, self.meta())
        self.out(404, {"error": "nf"})

    def do_POST(self):
        u = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(n)
        if u == "/test/bump_on_next_put":
            BUMP["on"] = True
            return self.out(200, {"ok": True})
        if u == "/test/pi_edit":  # 测试钩子：模拟 Liang Hu 在网页 Word 里保存了新内容（不经工作台）
            with L:
                add_version(data)
                return self.out(200, {"ok": True, "eTag": etag()})
        if not self.auth():
            return
        with L:
            pre = f"/v1.0/me/drive/items/{ITEM}/versions/"
            if u.startswith(pre) and u.endswith("/restoreVersion"):
                vid = u[len(pre):-len("/restoreVersion")]
                v = next((x for x in VERS if x["id"] == vid), None)
                if not v:
                    return self.out(404, {"error": "no version"})
                add_version(open(v["file"], "rb").read())
                return self.out(204)
        self.out(404, {"error": "nf"})


ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
