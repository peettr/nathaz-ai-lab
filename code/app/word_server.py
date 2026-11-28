#!/usr/bin/env python3
"""L26.25 第三步：原生 Word 稿（个人 OneDrive）工作台。
- 左栏：本地渲染的只读预览（pandoc docx→HTML，显示修订），不用公开链接；编辑另开网页 Word。
- 右栏：沿用 server.py 的对话读取、【稿件工作台】发问与 60 s 去重、wb-edit 建议解析。
- 接受：取最新版本 → 写成 w:ins/w:del 修订＋批注 → 核对非文字部件不变 → If-Match 条件覆盖（成为 OneDrive 新版本）；412 就停下报出。
- 撤销：按本次写入的作者＋时间戳拒绝自己的修订、删批注，再条件覆盖；版本历史可列出与恢复。
用法：word_server.py <config.json>
"""
import hashlib, io, json, os, re, shutil, subprocess, sys, threading, time, zipfile
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

APP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP)
import server as S  # noqa: E402  复用对话/发问/去重/建议解析（读同一个 config）
import gdoc as GD  # noqa: E402
from graph import Graph, GraphError  # noqa: E402
from ooxml_suggest import Doc, runs_of, accept_reject  # noqa: E402

CFG, WS, LOCK = S.CFG, S.WS, S.LOCK
AUTHOR = CFG.get("revision_author", "Lead")
G = Graph(base=CFG.get("graph_base", "https://graph.microsoft.com/v1.0"), cred_dir=CFG.get("cred_dir", "~/.config/l26-25-workbench"),
          test_token=[已隐去]"graph_test_token"))
CUR = os.path.join(WS, "current.docx")
PREVIEW = os.path.join(WS, "preview.html")
DOCMETA = os.path.join(WS, "doc_meta.json")
PANDOC = shutil.which("pandoc") or os.path.expanduser("~/.local/bin/pandoc")
TEXTUAL = re.compile(r"word/(document|header\d*|footer\d*|comments)\.xml$|word/_rels/document\.xml\.rels$|\[Content_Types\]\.xml$")

S.FORMAT_HINT = ("（工作台约定：若建议改稿，请在回复末尾每条修改附一个代码块，首行 ```wb-edit ，内容一行 JSON："
                 "{\"file\":\"word\",\"old\":\"Word 稿里逐字原句（须全文唯一）\",\"new\":\"新句\",\"why\":\"一句理由\"}，以 ``` 结束。"
                 "Liang Hu 在工作台点「接受」后，会以修订（可在 Word 里逐条接受/拒绝）加批注的形式写进他的 Word 原稿。）")


# ---------------- 稿件配置与缓存 ----------------
def doc_cfg():
    try:
        return json.load(open(os.path.join(WS, "private.json"), encoding="utf-8")).get("word_doc") or {}
    except (OSError, ValueError):
        return CFG.get("word_doc") or {}


_chat_messages, _chat_post = S.chat_messages, S.chat_post


def bound_topic():
    t = (doc_cfg().get("topic") or "").strip()
    return t if re.fullmatch(r"[0-9a-f]{8}(-[0-9a-f-]{4,})?", t) else ("fake" if CFG.get("chat") == "fake" else "")


def chat_messages(limit=40):
    t = bound_topic()
    if not t:
        return []  # 未绑定对话时绝不按空前缀查（会匹配全部对话）
    CFG["topic"] = t
    return _chat_messages(limit)


def chat_post(text):
    t = bound_topic()
    if not t:
        return 1, "这份 Word 稿还没绑定对话：请在「授权 / 选稿」页填对话前缀"
    CFG["topic"] = t
    return _chat_post(text)


S.chat_messages, S.chat_post = chat_messages, chat_post


def topic_check(prefix):
    """只读核对对话前缀：必须恰好对应一个 RC 对话。"""
    import sqlite3
    if not re.fullmatch(r"[0-9a-f]{8}", prefix or ""):
        return False, "对话前缀应是 8 位（如 720a2c2f）"
    if CFG.get("chat") == "fake":
        return True, prefix
    db = sqlite3.connect(f"file:{S.RCDB}?mode=ro", uri=True, timeout=10)
    try:
        ids = [r[0] for r in db.execute("select distinct topic_id from messages where topic_id like ?", (prefix + "%",))]
    finally:
        db.close()
    if len(ids) != 1:
        return False, f"前缀 {prefix} 对应 {len(ids)} 个对话（须恰好 1 个）"
    return True, ids[0]


def set_doc(item, topic=None):
    p = os.path.join(WS, "private.json")
    try:
        d = json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    d["word_doc"] = {"item_id": item["id"], "name": item.get("name", ""), "webUrl": item.get("webUrl", ""),
                     "topic": topic if topic is not None else (d.get("word_doc") or {}).get("topic", "")}
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)


def load_meta():
    try:
        return json.load(open(DOCMETA, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def paras_text(path):
    d = Doc(path)
    return ["".join(t for _, t in runs_of(p)) for _, p in d.paragraphs()]


def render_preview():
    tmp = PREVIEW + ".tmp"
    r = subprocess.run([PANDOC, CUR, "--track-changes=all", "-s", "--embed-resources", "-o", tmp,
                        "--metadata", "pagetitle=预览"], capture_output=True, text=True, timeout=120)
    if r.returncode == 0:
        css = ("<style>body{max-width:820px;margin:24px auto;font:15px/1.6 Georgia,'Times New Roman',serif;color:#222;padding:0 24px}"
               "img{max-width:100%}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:3px 6px}"
               ".insertion{background:#d9f5e1;color:#0f5b28;text-decoration:underline}.deletion{background:#fde2e1;color:#8a1c1c;text-decoration:line-through}"
               ".comment-start{border-bottom:2px solid #f0b400}.paragraph-insertion,.paragraph-deletion{}</style>")
        h = open(tmp, encoding="utf-8").read().replace("</head>", css + "</head>", 1)
        import html as _h

        def _cm(m):  # 批注正文不混进句子：换成小气泡，鼠标停上去看内容
            au = re.search(r'data-author="([^"]*)"', m.group(1))
            txt = _h.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
            return f'<span class="cm" title="{_h.escape((au.group(1) + "：" if au else "") + txt)}">💬</span>'
        h = re.sub(r'<span class="comment-start"([^>]*)>(.*?)</span>', _cm, h, flags=re.S)
        h = h.replace("</style></head>", ".cm{cursor:help;font-size:12px;vertical-align:super}</style></head>", 1)
        open(PREVIEW, "w", encoding="utf-8").write(h)
        os.remove(tmp)
    return r.returncode == 0, r.stderr[-300:]


def fetch(force=False):
    """取 OneDrive 上的最新版本（eTag 变了才下载），刷新预览。调用方不必持锁。"""
    dc = doc_cfg()
    if not dc.get("item_id"):
        return False, "还没选 Word 稿"
    it = G.item(dc["item_id"])
    m = load_meta()
    if force or it["eTag"] != m.get("eTag") or not os.path.exists(CUR):
        data = G.download(dc["item_id"])
        open(CUR + ".tmp", "wb").write(data)
        os.replace(CUR + ".tmp", CUR)
        ok, err = render_preview()
        m = {"eTag": it["eTag"], "modified": it.get("lastModifiedDateTime", ""), "fetched": time.strftime("%m-%d %H:%M"),
             "name": it.get("name"), "webUrl": it.get("webUrl"), "preview_ok": ok, "preview_err": "" if ok else err,
             "stamp": hashlib.sha1(data).hexdigest()[:10]}
        json.dump(m, open(DOCMETA, "w", encoding="utf-8"), ensure_ascii=False)
    else:
        m["fetched"] = time.strftime("%m-%d %H:%M")
        json.dump(m, open(DOCMETA, "w", encoding="utf-8"), ensure_ascii=False)
    return True, "已取最新"


BACK = os.path.join(WS, "backups")


def backup(data, tag):
    """写回前把当时的版本存一份到本机（OneDrive 版本历史之外的第二道保险，只留最近 30 份）。"""
    os.makedirs(BACK, exist_ok=True)
    fn = os.path.join(BACK, time.strftime("%Y%m%d-%H%M%S") + "_" + re.sub(r"[^0-9A-Za-z]", "", tag)[-8:] + ".docx")
    open(fn, "wb").write(data)
    fs = sorted(os.listdir(BACK))
    for f in fs[:-30]:
        os.remove(os.path.join(BACK, f))
    return os.path.basename(fn)


def integrity(before_bytes, after_path):
    """写回前核对：非文字部件（图片、样式、编号、主题……）逐字节不变；XML 可解析。"""
    from lxml import etree
    zb, za = zipfile.ZipFile(io.BytesIO(before_bytes)), zipfile.ZipFile(after_path)
    for n in zb.namelist():
        if not TEXTUAL.match(n) and zb.read(n) != za.read(n):
            return False, f"部件 {n} 有变化"
    for n in za.namelist():
        if n.endswith((".xml", ".rels")):
            etree.fromstring(za.read(n))
    return True, "ok"


# ---------------- 待批项 ----------------
def word_locate(sel, page):
    if not sel or not os.path.exists(CUR):
        return None
    key = " ".join(sel.split())[:120]
    for i, t in enumerate(paras_text(CUR), 1):
        if key and key[:60] in " ".join(t.split()):
            return {"file": (load_meta().get("name") or "Word 稿"), "line": i, "score": 1}
    return None


S.locate = word_locate


def edits_view(st):
    msgs = S.chat_messages(200)
    eds = S.pending_edits(msgs, st)
    paras = [" ".join(t.split()) for t in paras_text(CUR)] if os.path.exists(CUR) else []
    plain = " ".join(paras)
    for e in eds:
        if "error" in e:
            continue
        if e["status"] in ("待批", "需重新确认") and plain:
            o, n = " ".join(e["old"].split()), " ".join(e["new"].split())
            if o in plain:
                e["status"] = "待批"
                e["line"] = next((i for i, t in enumerate(paras, 1) if o in t), None)
            elif n in plain:
                e["status"] = "已在稿中"
            else:
                e["status"] = "需重新确认"
                e["note"] = "原句已被别的修改改动（或稿里找不到），请 Lead 按最新稿重给这一条"
        d = st["decisions"].get(e["id"]) or {}
        if d.get("version"):
            e["commit"] = "版本 " + d["version"]
    # Liang Hu 在 Word 里写的批注（作者不是 Lead）
    if os.path.exists(CUR):
        _, comments = GD.parse_docx(CUR)
        for c in comments:
            if c["author"] == AUTHOR:
                continue
            cid = "c-" + hashlib.sha1((c["anchor"] + "|" + c["text"]).encode()).hexdigest()[:10]
            d = st["decisions"].get(cid)
            eds.append({"id": cid, "kind": "comment", "source": "word", "plain_old": c["anchor"], "comment": c["text"],
                        "author": c["author"], "status": d["status"] if d else "批注", "why": "Word 里的批注"})
    return eds


# ---------------- 接受 / 撤销 / 版本 ----------------
def accept(eid):
    with LOCK:
        st = S.load_state()
        eds = {e["id"]: e for e in edits_view(st)}
        e = eds.get(eid)
        if not e or "error" in e or e.get("kind") == "comment":
            return {"ok": False, "msg": "找不到这条建议或格式有误"}
        if e["status"] not in ("待批", "失败", "需重新确认"):
            return {"ok": False, "msg": f"这条已是「{e['status']}」"}
        dc = doc_cfg()
        try:
            it = G.item(dc["item_id"])  # 先取最新版本与 eTag
            etag = it["eTag"]
            data = G.download(dc["item_id"])
        except GraphError as ex:
            return {"ok": False, "msg": "取 Word 稿失败：" + str(ex)[:200]}
        tmp_in, tmp_out = os.path.join(WS, "w_in.docx"), os.path.join(WS, "w_out.docx")
        open(tmp_in, "wb").write(data)
        # 时间戳是撤销时找回本次修订的钥匙，必须每次不同（Word 只保留到秒）
        last = max([0] + [dd.get("stamp_t", 0) for dd in st["decisions"].values()])
        t = max(int(time.time()), last + 1)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
        when = time.strftime("%Y-%m-%d %H:%M")
        d = Doc(tmp_in)
        ok, msg = d.suggest(e["old"], e["new"], f"Lead 建议，Liang Hu {when} 在工作台接受：{e.get('why', '')}", AUTHOR, stamp)
        if not ok:
            st["decisions"][eid] = {"status": "失败", "note": "没写入：" + msg + "（可能已过时，请 Lead 按最新稿重给）", "when": when}
            S.save_state(st)
            return {"ok": False, "msg": "没写入 Word：" + msg}
        d.save(tmp_out)
        good, why = integrity(data, tmp_out)
        if not good:
            return {"ok": False, "msg": "写入后核对没通过，已放弃，没有上传：" + why}
        bk = backup(data, etag)
        try:
            r = G.upload_if_match(dc["item_id"], open(tmp_out, "rb").read(), etag)
        except GraphError as ex:
            if ex.status == 412:
                S.log(f"accept {eid}: 412 eTag 不符，停下")
                return {"ok": False, "msg": "Word 稿在这期间被改过（可能你正开着网页 Word 在编辑），为免覆盖，这次没有写入。请保存/关闭 Word 后点「刷新」再接受。"}
            return {"ok": False, "msg": "上传失败，Word 稿未变：" + str(ex)[:200]}
        newtag = r.get("eTag", "")
        ver = (G.versions(dc["item_id"]) or [{}])[0].get("id", "")
        st["decisions"][eid] = {"status": "已接受", "when": when, "stamp": stamp, "stamp_t": t, "version": ver, "prev_etag": etag, "etag": newtag,
                                "note": msg}
        st["history"].append({"id": eid, "when": when, "stamp": stamp, "version": ver, "old": e["old"], "new": e["new"]})
        S.save_state(st)
    S.log(f"accept {eid}: 已写入 Word 修订（{msg}），版本 {ver}")
    fetch(force=True)
    return {"ok": True, "msg": f"已写入 Word：{msg}（OneDrive 版本 {ver}；在 Word「审阅」里可逐条接受/拒绝）"}


def accept_many(ids):
    res = []
    for i in ids:
        r = accept(i)
        res.append({"id": i, "ok": r["ok"], "msg": r["msg"][:160]})
    ok = sum(1 for x in res if x["ok"])
    return {"ok": ok > 0, "msg": f"当前筛选的 {len(ids)} 条：写进 Word {ok} 条，未写 {len(ids) - ok} 条（未写的仍在列表里，原因见各条）", "results": res}


def revert(eid):
    with LOCK:
        st = S.load_state()
        dd = st["decisions"].get(eid)
        if not dd or dd.get("status") != "已接受":
            return {"ok": False, "msg": "这条不是已接受状态"}
        dc = doc_cfg()
        it = G.item(dc["item_id"])
        data = G.download(dc["item_id"])
        tmp_in, tmp_out = os.path.join(WS, "w_in.docx"), os.path.join(WS, "w_out.docx")
        open(tmp_in, "wb").write(data)
        d = Doc(tmp_in)
        n = d.remove_stamp(AUTHOR, dd["stamp"])
        if n == 0:
            return {"ok": False, "msg": "这条修订已在 Word 里被你接受或改动过，不能自动撤销；请在 Word 里直接改，或在「版本历史」里回滚。"}
        d.save(tmp_out)
        good, why = integrity(data, tmp_out)
        if not good:
            return {"ok": False, "msg": "撤销后核对没通过，没有上传：" + why}
        backup(data, it["eTag"])
        try:
            G.upload_if_match(dc["item_id"], open(tmp_out, "rb").read(), it["eTag"])
        except GraphError as ex:
            if ex.status == 412:
                return {"ok": False, "msg": "Word 稿刚被改过，为免覆盖没有撤销；请稍后刷新再试。"}
            return {"ok": False, "msg": "上传失败：" + str(ex)[:200]}
        dd.update({"status": "已撤销", "revert_when": time.strftime("%Y-%m-%d %H:%M")})
        S.save_state(st)
    fetch(force=True)
    return {"ok": True, "msg": f"已撤销（去掉了这条的 {n} 处修订/批注），Word 稿生成了一个新版本"}


def versions():
    dc = doc_cfg()
    out = []
    try:
        out = [{"id": v.get("id"), "time": v.get("lastModifiedDateTime", ""), "src": "onedrive"} for v in G.versions(dc["item_id"])]
    except GraphError as ex:
        S.log(f"versions api: {str(ex)[:120]}")
    if os.path.isdir(BACK):  # 本机备份（写回前的版本），OneDrive 版本历史不可用时也能回滚
        for f in sorted(os.listdir(BACK), reverse=True):
            t = f[:15]
            out.append({"id": "local:" + f, "time": f"{t[:4]}-{t[4:6]}-{t[6:8]}T{t[9:11]}:{t[11:13]}:{t[13:15]}", "src": "本机备份（写回前）"})
    return out


def restore(vid):
    dc = doc_cfg()
    with LOCK:
        if vid.startswith("local:"):
            fn = os.path.join(BACK, os.path.basename(vid[6:]))
            it = G.item(dc["item_id"])
            G.upload_if_match(dc["item_id"], open(fn, "rb").read(), it["eTag"])
        else:
            G.restore_version(dc["item_id"], vid)
    fetch(force=True)
    S.log(f"restore version {vid}")
    return {"ok": True, "msg": f"已恢复到版本 {vid}（OneDrive 把它存成新的当前版本，之前的版本仍在历史里）"}


def comment_action(body):
    eid, act = body.get("id", ""), body.get("act", "")
    with LOCK:
        st = S.load_state()
        e = {x["id"]: x for x in edits_view(st)}.get(eid)
    if not e or e.get("kind") != "comment":
        return {"ok": False, "msg": "找不到这条批注"}
    if act == "tolead":
        r = S.ask({"question": f"Word 稿里有一条批注（{e.get('author') or 'Liang Hu'}）：「{e['comment']}」，请按批注给修改建议。",
                   "selection": e.get("plain_old", ""), "page": None})
        if not r["ok"]:
            return r
        new = "已交 Lead"
    elif act == "done":
        new = "已处理"
    else:
        return {"ok": False, "msg": "未知操作"}
    with LOCK:
        st = S.load_state()
        st["decisions"][eid] = {"status": new, "when": time.strftime("%m-%d %H:%M")}
        S.save_state(st)
    return {"ok": True, "msg": "已发给 Lead" if new == "已交 Lead" else "已标为处理过"}


def loop():
    while True:
        try:
            if doc_cfg().get("item_id") and G.status().get("authorized"):
                fetch()
        except Exception as ex:
            S.log(f"word fetch loop: {str(ex)[:200]}")
        time.sleep(int(CFG.get("word_interval", 120)))


# ---------------- HTTP ----------------
class H(S.H):
    def do_GET(self):
        u = urlparse(self.path).path
        if u in ("/", "/index.html"):
            return self.send(200, open(os.path.join(APP, "static", "word.html"), "rb").read(), "text/html; charset=utf-8")
        if u == "/auth":
            return self.send(200, open(os.path.join(APP, "static", "word_auth.html"), "rb").read(), "text/html; charset=utf-8")
        if u == "/preview":
            if not os.path.exists(PREVIEW):
                return self.send(200, "<p style='font-family:sans-serif;color:#666'>还没有预览：先在「授权」页授权并选好 Word 稿。</p>", "text/html; charset=utf-8")
            return self.send(200, open(PREVIEW, "rb").read(), "text/html; charset=utf-8")
        if u == "/api/state":
            st = S.load_state()
            try:
                msgs, err = S.chat_messages(40), ""
            except Exception as ex:
                msgs, err = [], str(ex)
            m = load_meta()
            return self.send(200, {"title": CFG.get("title", ""), "mode": CFG.get("mode", ""), "chat": msgs[-20:], "chat_error": err,
                                   "auth": {k: v for k, v in G.status().items()}, "topic": bound_topic()[:8], "doc": {**doc_cfg(), **{k: m.get(k) for k in ("eTag", "modified", "fetched", "stamp", "preview_ok", "preview_err")}},
                                   "edits": edits_view(st) if not err else []})
        if u == "/api/w_versions":
            try:
                return self.send(200, {"ok": True, "versions": versions()})
            except Exception as ex:
                return self.send(200, {"ok": False, "msg": S.mask(str(ex))[:200]})
        if u.startswith("/static/"):
            return super().do_GET()
        return self.send(404, {"msg": "not found"})

    def do_POST(self):
        u = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            body = {}
        try:
            if u == "/api/ask":
                return self.send(200, S.ask(body))
            if u == "/api/accept":
                return self.send(200, accept(body.get("id", "")))
            if u == "/api/accept_many":
                return self.send(200, accept_many([str(x) for x in body.get("ids", [])][:100]))
            if u == "/api/reject":
                return self.send(200, S.reject(body.get("id", "")))
            if u == "/api/revert":
                return self.send(200, revert(body.get("id", "")))
            if u == "/api/refresh":
                ok, msg = fetch(force=True)
                return self.send(200, {"ok": ok, "msg": msg})
            if u == "/api/w_comment":
                return self.send(200, comment_action(body))
            if u == "/api/w_restore":
                return self.send(200, restore(body.get("version", "")))
            if u == "/api/w_auth/client_id":
                G.set_client_id(body.get("client_id", "").strip())
                return self.send(200, {"ok": True, "msg": "已保存应用 ID"})
            if u == "/api/w_auth/start":
                return self.send(200, {"ok": True, **G.start_device_code()})
            if u == "/api/w_auth/poll":
                return self.send(200, {"ok": True, **G.poll_device_code()})
            if u == "/api/w_settopic":
                ok, tid = topic_check(body.get("topic", "").strip())
                if not ok:
                    return self.send(200, {"ok": False, "msg": tid})
                p = os.path.join(WS, "private.json")
                try:
                    d = json.load(open(p, encoding="utf-8"))
                except (OSError, ValueError):
                    d = {}
                d.setdefault("word_doc", {})["topic"] = tid
                json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
                return self.send(200, {"ok": True, "msg": f"已绑定对话 {tid[:8]}"})
            if u == "/api/w_setdoc":
                it = G.resolve_link(body.get("link", ""))
                if not (it.get("name", "").lower().endswith(".docx")):
                    return self.send(200, {"ok": False, "msg": f"这不是 .docx 文件：{it.get('name')}"})
                set_doc(it)
                fetch(force=True)
                return self.send(200, {"ok": True, "msg": f"已选定：{it.get('name')}"})
        except (GraphError, ValueError) as ex:
            return self.send(200, {"ok": False, "msg": S.mask(str(ex))[:300]})
        except Exception as ex:
            S.log(f"error {u}: {ex}")
            return self.send(200, {"ok": False, "msg": "出错：" + S.mask(str(ex))[:300]})
        return self.send(404, {"msg": "not found"})


def main():
    for host in CFG["bind"]:
        s = ThreadingHTTPServer((host, int(CFG["port"])), H)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        S.log(f"word listening {host}:{CFG['port']} mode={CFG.get('mode')}")
    threading.Thread(target=loop, daemon=True).start()
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
