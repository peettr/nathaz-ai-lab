"""L26.25 · 个人 OneDrive（Microsoft Graph）最小客户端：设备码授权、取文件与 eTag、If-Match 条件覆盖、版本历史。

只用标准库。令牌只存在 CRED_DIR（默认 ~/.config/l26-25-workbench/，目录 700、文件 600）；本模块不打印、不记日志任何令牌。
测试时 base 指向本地模拟服务（mock_graph.py），token 用固定测试值。
"""
import json, os, re, time, urllib.error, urllib.parse, urllib.request, base64

AUTH = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
SCOPE = "Files.ReadWrite offline_access User.Read"


class GraphError(Exception):
    def __init__(self, status, msg):
        super().__init__(f"{status} {msg}")
        self.status = status


class Graph:
    def __init__(self, base="https://graph.microsoft.com/v1.0", cred_dir="~/.config/l26-25-workbench", test_token=[已隐去]
        self.base = base.rstrip("/")
        self.cred_dir = os.path.expanduser(cred_dir)
        self.test_token = [已隐去]
        self._pending = None  # 设备码流程进行中

    # ---------- 凭据 ----------
    def _p(self, n):
        return os.path.join(self.cred_dir, n)

    def _read(self, n):
        try:
            return json.load(open(self._p(n), encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _write(self, n, d):
        os.makedirs(self.cred_dir, mode=0o700, exist_ok=True)
        os.chmod(self.cred_dir, 0o700)
        tmp = self._p(n + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, self._p(n))
        os.chmod(self._p(n), 0o600)

    def client_id(self):
        return self._read("app.json").get("client_id", "")

    def set_client_id(self, cid):
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", cid or ""):
            raise ValueError("应用（客户端）ID 格式不对：应是 36 位的 xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        d = self._read("app.json")
        d["client_id"] = cid
        self._write("app.json", d)

    def status(self):
        if self.test_token:
            [已隐去] {"client_id": True, "authorized": True, "who": "测试"}
        t = self._read("token.json")
        return {"client_id": bool(self.client_id()), "authorized": bool(t.get("refresh_token")), "who": t.get("who", ""),
                "pending": bool(self._pending), "user_code": (self._pending or {}).get("user_code"),
                "verification_uri": (self._pending or {}).get("verification_uri")}

    def _post_form(self, url, data):
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read())
            except ValueError:
                return {"error": f"http {e.code}"}

    def start_device_code(self):
        cid = self.client_id()
        if not cid:
            raise ValueError("还没填应用（客户端）ID")
        r = self._post_form(AUTH + "/devicecode", {"client_id": cid, "scope": SCOPE})
        if "device_code" not in r:
            raise ValueError("设备码申请失败：" + str(r.get("error_description") or r.get("error"))[:200])
        r["t0"] = time.time()
        self._pending = r
        return {"user_code": r["user_code"], "verification_uri": r["verification_uri"], "expires_in": r.get("expires_in")}

    def poll_device_code(self):
        """前端每 5 秒调一次；授权完成后存令牌。"""
        p = self._pending
        if not p:
            return {"done": False, "msg": "没有进行中的授权"}
        if time.time() - p["t0"] > p.get("expires_in", 900):
            self._pending = None
            return {"done": False, "msg": "短码已过期，请重新开始"}
        r = self._post_form(AUTH + "/token", {"grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                                              "client_id": self.client_id(), "device_code": p["device_code"]})
        if r.get("error") in ("authorization_pending", "slow_down"):
            return {"done": False, "msg": "等你在浏览器里完成登录和同意…"}
        if "access_token" not in r:
            self._pending = None
            return {"done": False, "msg": "授权失败：" + str(r.get("error_description") or r.get("error"))[:200]}
        self._save_token(r)
        self._pending = None
        try:
            me = self.get_json("/me")
            t = self._read("token.json")
            t["who"] = me.get("userPrincipalName") or me.get("displayName") or ""
            self._write("token.json", t)
        except Exception:
            pass
        return {"done": True, "msg": "授权完成"}

    def _save_token(self, r):
        t = self._read("token.json")
        t.update({"access_token": r["access_token"], "expires_at": time.time() + int(r.get("expires_in", 3600)) - 120})
        if r.get("refresh_token"):
            t["refresh_token"] = r["refresh_token"]
        self._write("token.json", t)

    def token(self):
        if self.test_token:
            [已隐去] self.test_token
        t = self._read("token.json")
        if not t.get("refresh_token"):
            raise GraphError(401, "还没授权，请在工作台「授权」页完成一次设备码登录")
        if time.time() < t.get("expires_at", 0):
            return t["access_token"]
        r = self._post_form(AUTH + "/token", {"grant_type": "refresh_token", "client_id": self.client_id(),
                                              "refresh_token": t["refresh_token"], "scope": SCOPE})
        if "access_token" not in r:
            raise GraphError(401, "授权已失效，请在「授权」页重新登录一次（" + str(r.get("error"))[:60] + "）")
        self._save_token(r)
        return r["access_token"]

    # ---------- Graph 调用 ----------
    def _req(self, method, path, body=None, headers=None, raw=False, timeout=120):
        url = path if path.startswith("http") else self.base + path
        h = {"Authorization": "Bearer " + self.token()}
        h.update(headers or {})
        req = urllib.request.Request(url, data=body, method=method, headers=h)
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            data = resp.read()
            return (data, dict(resp.headers)) if raw else (json.loads(data) if data else {})
        except urllib.error.HTTPError as e:
            txt = e.read()[:300].decode("utf-8", "replace")
            raise GraphError(e.code, txt)

    def get_json(self, path):
        return self._req("GET", path)

    def item(self, item_id):
        return self.get_json(f"/me/drive/items/{item_id}")

    def download(self, item_id):
        data, _ = self._req("GET", f"/me/drive/items/{item_id}/content", raw=True)
        return data

    def upload_if_match(self, item_id, data, etag):
        """条件覆盖：eTag 不符返回 412（GraphError.status==412），不覆盖。覆盖成为 OneDrive 新版本。"""
        h = {"If-Match": etag, "Content-Type": "application/octet-stream"}
        if len(data) <= 4 * 1024 * 1024:
            return self._req("PUT", f"/me/drive/items/{item_id}/content", body=data, headers=h)
        s = self._req("POST", f"/me/drive/items/{item_id}/createUploadSession",
                      body=json.dumps({"item": {"@microsoft.graph.conflictBehavior": "replace"}}).encode(),
                      headers={"If-Match": etag, "Content-Type": "application/json"})
        url, n, CH = s["uploadUrl"], len(data), 5 * 1024 * 1024
        res = {}
        for a in range(0, n, CH):
            b = min(n, a + CH)
            req = urllib.request.Request(url, data=data[a:b], method="PUT",
                                         headers={"Content-Range": f"bytes {a}-{b - 1}/{n}", "Content-Length": str(b - a)})
            res = json.loads(urllib.request.urlopen(req, timeout=300).read() or b"{}")
        return res

    def versions(self, item_id):
        return self.get_json(f"/me/drive/items/{item_id}/versions").get("value", [])

    def restore_version(self, item_id, version_id):
        return self._req("POST", f"/me/drive/items/{item_id}/versions/{version_id}/restoreVersion", body=b"",
                         headers={"Content-Type": "application/json"})

    def resolve_link(self, link):
        """把 Liang Hu 粘贴的 OneDrive 链接（分享链接或编辑页网址）解析成文件编号。"""
        m = re.search(r"[?&](?:resid|id)=([^&]+)", link)
        if m and "!" in urllib.parse.unquote(m.group(1)):
            return self.item(urllib.parse.unquote(m.group(1)))
        enc = "u!" + base64.urlsafe_b64encode(link.strip().encode()).decode().rstrip("=")
        return self.get_json(f"/shares/{enc}/driveItem")
