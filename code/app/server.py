import difflib
#!/usr/bin/env python3
"""L26.25 稿件工作台原型（快试，独立于 Research Chat 正式代码）。
- 只用标准库；监听 config.json 里的地址（127.0.0.1 与 Tailscale）。
- 读对话：RC 库只读连接（mode=ro）；发问：~/bin/rc_post.py（以 Liang Hu 身份，前缀【稿件工作台】）。
- 写稿：只调 ~/bin/doc-git-sync（拉/提交推送）；本程序不读、不打印任何 Overleaf 令牌；所有 git/命令输出先掩码 olp_。
- 编译：工作站 已装的 tectonic。
用法：server.py <config.json>
"""
import zipfile, gzip, html, json, os, re, shutil, sqlite3, subprocess, sys, threading, time, uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdoc as GD  # noqa: E402

APP = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(sys.argv[1], encoding="utf-8"))
REPO = os.path.expanduser(CFG["repo"])
MAIN = CFG.get("main", "main.tex")
WS = os.path.expanduser(CFG["workdir"])
BUILD = os.path.join(WS, "build")
STATE = os.path.join(WS, "state.json")
LOG = os.path.join(WS, "workbench.log")
DOCSYNC = os.path.expanduser("~/bin/doc-git-sync")
RCPOST = os.path.expanduser("~/bin/rc_post.py")
RCDB = os.path.expanduser("~/projects/research-chat-v2/data/research-chat.sqlite")
TECTONIC = os.path.expanduser("~/.local/bin/tectonic")
LOCK = threading.Lock()
os.makedirs(BUILD, exist_ok=True)

FORMAT_HINT = ("（工作台约定：若建议改稿，请在回复末尾每条修改附一个代码块，首行 ```wb-edit ，"
               "内容一行 JSON：{\"file\":\"" + MAIN + "\",\"old\":\"源码里逐字原句（须唯一可搜）\",\"new\":\"新句\",\"why\":\"一句理由\"}，"
               "以 ``` 结束。Liang Hu 在工作台点「接受」后才会写回 Overleaf。）")


def private_view():
    """Google 文档链接等只存在工作目录 private.json（不进公开代码目录）。"""
    try:
        d = json.load(open(os.path.join(WS, "private.json"), encoding="utf-8"))
        return {"gdoc_url": d.get("gdoc_url", ""), "gdoc_label": d.get("gdoc_label", ""), "_src": d.get("gdoc_source")}
    except (OSError, ValueError):
        return {"gdoc_url": "", "gdoc_label": "", "_src": None}


def mask(s):
    return re.sub(r"olp_[A-Za-z0-9]+", "olp_***", s or "")


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%m-%d %H:%M:%S ") + mask(msg) + "\n")


def run(cmd, cwd=None, env=None, timeout=300):
    e = dict(os.environ)
    e["GIT_TERMINAL_PROMPT"] = "0"
    if env:
        e.update(env)
    p = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True, timeout=timeout)
    out = mask((p.stdout or "") + (p.stderr or ""))
    log(f"$ {' '.join(os.path.basename(c) if i == 0 else c for i, c in enumerate(cmd))[:200]} -> {p.returncode} {out.strip()[:400]}")
    return p.returncode, out


def git(*a):
    return run(["git", *a], cwd=REPO)


def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        return {"decisions": {}, "history": [], "asks": []}


def save_state(st):
    tmp = STATE + ".tmp"
    json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


# ---------------- 编译与 synctex ----------------
def compile_to(outdir):
    os.makedirs(outdir, exist_ok=True)
    rc, out = run([TECTONIC, "-X", "compile", "--synctex", "--outdir", outdir, MAIN], cwd=REPO, timeout=300)
    pdf = os.path.join(outdir, os.path.splitext(MAIN)[0] + ".pdf")
    return rc == 0 and os.path.exists(pdf), out, pdf


def pdf_pages(pdf):
    try:
        data = open(pdf, "rb").read()
        return len(re.findall(rb"/Type\s*/Page[^s]", data))
    except OSError:
        return 0


def synctex_page_lines():
    """返回 {页号: set(主文件行号)}；解析失败返回 {}。"""
    p = os.path.join(BUILD, os.path.splitext(MAIN)[0] + ".synctex.gz")
    res, tags, page = {}, set(), 0
    try:
        for ln in gzip.open(p, "rt", encoding="utf-8", errors="replace"):
            if ln.startswith("Input:"):
                parts = ln.strip().split(":", 2)
                if len(parts) == 3 and os.path.basename(parts[2]) == os.path.basename(MAIN):
                    tags.add(parts[1])
            elif ln.startswith("{"):
                try:
                    page = int(ln[1:])
                except ValueError:
                    pass
            else:
                m = re.match(r"^[hvxkg$(\[](\d+),(\d+):", ln)
                if m and m.group(1) in tags and page:
                    res.setdefault(page, set()).add(int(m.group(2)))
    except OSError:
        return {}
    return res


def words(s):
    return re.findall(r"[A-Za-z0-9]+", s.lower())


def locate(sel, page):
    """在主文件里找选中文字所在行：按词序最长连续匹配打分，优先该页 synctex 覆盖的行。"""
    try:
        lines = open(os.path.join(REPO, MAIN), encoding="utf-8").read().split("\n")
    except OSError:
        return None
    sw = words(sel)
    if not sw:
        return None
    pl = synctex_page_lines().get(int(page or 0), set())
    best = (0, None)
    for i, line in enumerate(lines, 1):
        lw = words(re.sub(r"\\[a-zA-Z]+", " ", line))
        if not lw:
            continue
        # 最长公共连续词串
        score, L = 0, set()
        for k in range(len(sw)):
            for j in range(len(lw)):
                n = 0
                while k + n < len(sw) and j + n < len(lw) and sw[k + n] == lw[j + n]:
                    n += 1
                score = max(score, n)
        score = score + (0.5 if (not pl or i in pl) else 0)
        if score > best[0]:
            best = (score, i)
    if best[1] is None or best[0] < 1.5:
        return None
    return {"file": MAIN, "line": best[1], "score": best[0]}


# ---------------- 对话后端 ----------------
def chat_messages(limit=40):
    if CFG.get("chat") == "fake":
        p = os.path.join(WS, "fake_chat.jsonl")
        msgs = []
        if os.path.exists(p):
            for ln in open(p, encoding="utf-8"):
                if ln.strip():
                    msgs.append(json.loads(ln))
        return msgs[-limit:]
    db = sqlite3.connect(f"file:{RCDB}?mode=ro", uri=True, timeout=10)
    try:
        rows = db.execute(
            "select message_id, role, ts, content from messages where topic_id like ? and orphan=0 and is_reset=0 "
            "and (role='user' or done=1) and content<>'' order by ts desc, (role='assistant') desc, rowid desc limit ?", (CFG["topic"] + "%", limit)).fetchall()
    finally:
        db.close()
    return [{"id": r[0], "role": r[1], "ts": r[2], "content": r[3]} for r in reversed(rows)]


def chat_post(text):
    if CFG.get("chat") == "fake":
        time.sleep(float(CFG.get("fake_post_delay", 0)))  # 仅测试：模拟 rc_post 等待送达的耗时
        with open(os.path.join(WS, "fake_chat.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": "u-" + uuid.uuid4().hex[:8], "role": "user", "ts": time.time(), "content": text},
                               ensure_ascii=False) + "\n")
        return 0, "posted(fake)"
    tmp = os.path.join(WS, f"post_{uuid.uuid4().hex[:8]}.txt")
    open(tmp, "w", encoding="utf-8").write(text)
    rc, out = run(["python3", RCPOST, CFG["topic"], tmp], env={"RC_POST_WAIT": "20"}, timeout=120)
    os.remove(tmp)
    return rc, out.strip()[-300:]


EDIT_RE = re.compile(r"```wb-edit\s*\n(.*?)\n?```", re.S)


def pending_edits(msgs, st):
    out = []
    for m in msgs:
        if m["role"] != "assistant":
            continue
        for k, blk in enumerate(EDIT_RE.findall(m["content"])):
            eid = f"{m['id']}#{k}"
            try:
                e = json.loads(blk.strip())
                e = {"file": str(e.get("file") or MAIN), "old": str(e["old"]), "new": str(e["new"]), "why": str(e.get("why", ""))}
            except (ValueError, KeyError, TypeError) as ex:
                e = {"error": f"格式无法解析：{ex}", "raw": blk[:500]}
            e["id"] = eid
            e["msg_ts"] = m.get("ts")
            d = st["decisions"].get(eid)
            e["status"] = d["status"] if d else "待批"
            if d:
                e.update({k2: d[k2] for k2 in ("commit", "note", "when") if k2 in d})
            out.append(e)
    # 待批的建议若原句已不在、新句已在稿中（Lead 已直接提交或别处已改）→ 标「已在稿中」，不再给接受按钮
    srcs = {}
    for e in out:
        if "error" in e or e["status"] != "待批":
            continue
        try:
            if e["file"] not in srcs:
                srcs[e["file"]] = open(safe_path(e["file"]), encoding="utf-8").read()
            t = srcs[e["file"]]
            a, _, _ = find_unique(t, e["old"])
            if a is not None:
                e["line"] = t[:a].count("\n") + 1
            elif find_unique(t, e["new"])[0] is not None:
                e["status"] = "已在稿中"
            else:
                e["status"] = "需重新确认"
                e["note"] = "原句已被别的修改改动（或稿里找不到），请 Lead 按最新稿重给这一条"
        except (OSError, ValueError):
            pass
    gs = st.get("gsync", {})
    for e in out:
        if e.get("id") in gs:
            e["gsync"] = gs[e["id"]].get("status")
            e["gsync_msg"] = gs[e["id"]].get("msg", "")
            if e["gsync"] == "需重新确认" and "new" in e:
                e["gsync_plain"] = "\n\n".join(tex2plain(x) for x in re.split(r"\n\s*\n", e["new"]))
    # 同一 file+old+new（空白归一）只留第一条可批；后来的标「重复」并合并计数，防止接受多次
    first = {}
    for e in out:
        if "error" in e:
            continue
        key = (e["file"], " ".join(e["old"].split()), " ".join(e["new"].split()))
        if key in first:
            f = first[key]
            f["dup_count"] = f.get("dup_count", 1) + 1
            if e["status"] in ("待批", "已在稿中"):
                e["status"] = "重复"
                e["dup_of"] = f["id"]
        else:
            first[key] = e
    return out


# ---------------- 稿件操作 ----------------
def ensure_clean():
    rc, out = git("status", "--porcelain")
    return rc == 0 and out.strip() == "", out


def pull():
    return run([DOCSYNC, REPO], timeout=180)


def find_unique(text, old):
    n = text.count(old)
    if n == 1:
        i = text.index(old)
        return i, i + len(old), "精确"
    if n > 1:
        return None, n, "定位不唯一"
    toks = old.split()
    if not toks:
        return None, 0, "原句为空"
    pat = r"\s+".join(re.escape(t) for t in toks)
    ms = list(re.finditer(pat, text))
    if len(ms) == 1:
        return ms[0].start(), ms[0].end(), "空白归一"
    return None, len(ms), ("定位不唯一" if ms else "已过时（源码里找不到原句）")


def safe_path(rel):
    p = os.path.realpath(os.path.join(REPO, rel))
    if not p.startswith(os.path.realpath(REPO) + os.sep):
        raise ValueError("文件不在稿件目录内")
    return p


def accept(eid):
    with LOCK:
        st = load_state()
        if eid.startswith("g-"):
            it = st.get("gdoc", {}).get("shown", {}).get(eid)
            e = None if not it or it["kind"] != "edit" else \
                {"file": MAIN, "old": it["old"], "new": it["new"], "why": it["why"], "status": gdoc_status(st, it)}
        else:
            msgs = chat_messages(200)
            eds = {e["id"]: e for e in pending_edits(msgs, st)}
            e = eds.get(eid)
        if eid.startswith("g-") and e is None:
            it = st.get("gdoc", {}).get("shown", {}).get(eid)
            if it:
                return {"ok": False, "msg": "这一条不能直接写回（冲突、批注或需 Lead 转写），请用卡片上的按钮处理"}
        if not e or "error" in e:
            return {"ok": False, "msg": "找不到这条建议或格式有误"}
        if e["status"] not in ("待批", "失败", "需重新确认"):
            return {"ok": False, "msg": f"这条已是「{e['status']}」"}
        clean, _ = ensure_clean()
        if not clean:
            return {"ok": False, "msg": "稿件目录有未提交改动（可能 Lead 正在改），未动稿，请稍后再试"}
        rc, out = pull()
        if rc != 0:
            return {"ok": False, "msg": "拉取 Overleaf 失败或有冲突，已停，没有动稿：" + out[-300:]}
        rc, prev = git("rev-parse", "HEAD")
        prev = prev.strip()
        path = safe_path(e["file"])
        text = open(path, encoding="utf-8").read()
        a, b, how = find_unique(text, e["old"])
        if a is None:
            st["decisions"][eid] = {"status": "失败", "note": how, "when": time.strftime("%m-%d %H:%M")}
            save_state(st)
            return {"ok": False, "msg": f"没写回：{how}。请 Lead 按最新稿重给这一条。"}
        open(path, "w", encoding="utf-8").write(text[:a] + e["new"] + text[b:])
        ok, cout, pdf = compile_to(os.path.join(WS, "build_check"))
        pages_before = pdf_pages(os.path.join(BUILD, os.path.splitext(MAIN)[0] + ".pdf"))
        if not ok or (pages_before and abs(pdf_pages(pdf) - pages_before) > 1):
            git("checkout", "--", e["file"])
            st["decisions"][eid] = {"status": "失败", "note": "改后编译不过，已还原", "when": time.strftime("%m-%d %H:%M")}
            save_state(st)
            return {"ok": False, "msg": "改后编译不过，已还原，没有提交：" + cout[-300:]}
        when = time.strftime("%Y-%m-%d %H:%M")
        if eid.startswith("g-"):
            msg = f"L26.25 工作台｜Google 文档改动 {eid}（Liang Hu 在 Google 文档改）｜Liang Hu {when} 接受｜{e['why'][:80]}"
        else:
            msg = f"L26.25 工作台｜{CFG.get('topic_label', CFG['topic'])} 建议 {eid[:8]}…（Lead 提）｜Liang Hu {when} 接受｜{e['why'][:80]}"
        rc, out = run([DOCSYNC, REPO, msg], timeout=180)
        if rc != 0:
            git("reset", "--hard", prev)  # 只丢弃本次刚做、未推出去的这一个提交
            st["decisions"][eid] = {"status": "失败", "note": "推送失败，本地已退回：" + out[-200:], "when": when}
            save_state(st)
            return {"ok": False, "msg": "推送失败，本地已退回，Overleaf 未变：" + out[-300:]}
        _, h = git("rev-parse", "--short", "HEAD")
        h = h.strip()
        st["decisions"][eid] = {"status": "已接受", "commit": h, "when": when, "note": how}
        st["history"].append({"id": eid, "commit": h, "when": when, "file": e["file"], "old": e["old"], "new": e["new"]})
        try:
            _gdoc_recompute(st)
        except Exception as ex:
            log(f"gdoc recompute after accept: {ex}")
        save_state(st)
        build_pdf()
        GSYNC_EVENT.set()
        return {"ok": True, "msg": f"已写回并推送：提交 {h}" + ("；正在同步到 Google 文档" if gdoc_source() and not eid.startswith("g-") else ""), "commit": h}


def reject(eid):
    with LOCK:
        st = load_state()
        st["decisions"][eid] = {"status": "已拒绝", "when": time.strftime("%m-%d %H:%M")}
        save_state(st)
    return {"ok": True, "msg": "已记为拒绝，未动稿"}


def revert(eid):
    with LOCK:
        st = load_state()
        d = st["decisions"].get(eid)
        if not d or d.get("status") != "已接受":
            return {"ok": False, "msg": "这条不是已接受状态"}
        clean, _ = ensure_clean()
        if not clean:
            return {"ok": False, "msg": "稿件目录有未提交改动，未撤销"}
        rc, out = pull()
        if rc != 0:
            return {"ok": False, "msg": "拉取失败或有冲突，已停：" + out[-300:]}
        rc, prev = git("rev-parse", "HEAD")
        prev = prev.strip()
        # 文字级反向替换：找当前稿里唯一的新句，换回原句（同一行有别的已接受修改时 git revert 会冲突，这样不会）
        h_ = next((x for x in reversed(st["history"]) if x["id"] == eid), None)
        if not h_:
            return {"ok": False, "msg": "找不到这条的写回记录，不能自动撤销"}
        path = safe_path(h_.get("file", "main.tex") if h_.get("file") else MAIN)
        text = open(path, encoding="utf-8").read()
        a, b, how = find_unique(text, h_["new"])
        if a is None:
            return {"ok": False, "msg": f"该处之后又被改过（{how}），不能自动撤销，请手动处理"}
        open(path, "w", encoding="utf-8").write(text[:a] + h_["old"] + text[b:])
        ok, cout, _ = compile_to(os.path.join(WS, "build_check"))
        if not ok:
            git("checkout", "--", ".")
            return {"ok": False, "msg": "撤销后编译不过，已还原，没有提交：" + cout[-300:]}
        when = time.strftime("%Y-%m-%d %H:%M")
        rc, out = run([DOCSYNC, REPO, f"L26.25 工作台｜撤销 {d['commit']}｜Liang Hu {when}"], timeout=180)
        if rc != 0:
            git("reset", "--hard", prev)
            return {"ok": False, "msg": "推送失败，本地已退回：" + out[-300:]}
        _, h = git("rev-parse", "--short", "HEAD")
        d.update({"status": "已撤销", "revert_commit": h.strip(), "when": when})
        save_state(st)
        build_pdf()
        return {"ok": True, "msg": f"已撤销：提交 {h.strip()}"}


# ---------------- Google 文档（只读） ----------------
GDOC_FILE = os.path.join(WS, "gdoc_latest.docx")
GDOC_LOCK = threading.Lock()
DONE = ("已接受", "已拒绝", "已忽略", "已处理", "已撤销")
DEFAULT_ST = {"edit": "待批", "need_lead": "需 Lead 转写", "conflict": "冲突待定", "comment": "批注"}


def gdoc_source():
    return CFG.get("gdoc_source") or private_view()["_src"]


def gdoc_fetch():
    src = gdoc_source()
    if not src:
        return False, "未配置 Google 文档"
    tmpd = os.path.join(WS, "gdoc_tmp_" + uuid.uuid4().hex[:6])
    os.makedirs(tmpd)
    try:
        dst = os.path.join(tmpd, "g.docx")
        if src["kind"] == "file":
            shutil.copy(os.path.expanduser(src["path"]), dst)
        else:  # rc-gdoc：只读取回
            rc, out = run([os.path.expanduser("~/bin/rc-gdoc"), "pull", src["path"], dst], timeout=120)
            if rc != 0 or not os.path.exists(dst):
                return False, "取 Google 文档失败：" + out[-200:]
        os.replace(dst, GDOC_FILE)
        return True, "ok"
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)


def _gdoc_recompute(st):
    """用已取回的 docx 与当前 LaTeX 重新算 Google 文档待批项（调用方持有 LOCK）。"""
    g = st.setdefault("gdoc", {"baseline": None, "shown": {}})
    if not os.path.exists(GDOC_FILE):
        return g
    paras, comments = GD.parse_docx(GDOC_FILE)
    src = open(os.path.join(REPO, MAIN), encoding="utf-8").read()
    items, nb, lag = GD.compute(paras, comments, g.get("baseline"), src, find_unique, locate)
    if CFG.get("doc_master", True):  # Google 文档为主稿：直接修改不进待批（由 msync 自动写进 LaTeX）
        items = [it for it in items if it["kind"] == "comment" or (not CFG.get("accept_tracked", True) and (it.get("origin") == "的建议修订"
                 or (it["kind"] == "conflict" and it.get("why", "").startswith("Google 文档里建议修订"))))]  # 建议修订默认已接受 → 由 msync 写进 LaTeX，不进待批
    g["baseline"], g["lag"] = nb, lag
    shown = g.setdefault("shown", {})
    live = {it["id"] for it in items}
    for it in items:
        it["live"] = True
        shown[it["id"]] = it
    for k in list(shown):
        if k not in live:
            if k in st["decisions"]:
                shown[k]["live"] = False
            else:
                del shown[k]
    g["pending"] = sum(1 for k, it in shown.items() if gdoc_status(st, it) not in DONE and it.get("live")
                       and not (it["kind"] == "comment" and gdoc_status(st, it) == "已交 Lead"))
    json.dump({"pending": g["pending"], "updated": time.strftime("%Y-%m-%d %H:%M"),
               "rule": "pending>0 时不要用 LaTeX 重新生成 Google 文档（会覆盖 Liang Hu 在 Google 文档里未处理的改动）"},
              open(os.path.join(WS, "gdoc_pending.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return g


def gdoc_status(st, it):
    d = st["decisions"].get(it["id"])
    return d["status"] if d else DEFAULT_ST[it["kind"]]


def gdoc_refresh():
    if not gdoc_source():
        return {"ok": False, "msg": "未配置 Google 文档"}
    with GDOC_LOCK:
        ok, msg = gdoc_fetch()
        with LOCK:
            st = load_state()
            st.setdefault("gdoc", {"baseline": None, "shown": {}})
            st["gdoc"]["fetched"] = time.strftime("%m-%d %H:%M")
            st["gdoc"]["msg"] = "" if ok else msg
            try:
                g = _gdoc_recompute(st)
            except Exception as ex:
                st["gdoc"]["msg"] = "解析 Google 文档出错：" + str(ex)[:200]
                g = st["gdoc"]
            save_state(st)
    return {"ok": ok, "msg": ("已取回 Google 文档" if ok else msg) + f"；待处理 {g.get('pending', 0)} 条"}


def gdoc_view(st):
    out = []
    try:
        lines = open(os.path.join(REPO, MAIN), encoding="utf-8").read().split("\n")
    except OSError:
        lines = []
    for it in st.get("gdoc", {}).get("shown", {}).values():
        e = dict(it)
        e["source"] = "gdoc"
        e["file"] = MAIN
        e["status"] = gdoc_status(st, it)
        if it["kind"] == "conflict" and it.get("line") and it["line"] <= len(lines):
            e["tex_text"] = lines[it["line"] - 1][:800]
        d = st["decisions"].get(it["id"])
        if d:
            e.update({k2: d[k2] for k2 in ("commit", "note", "when") if k2 in d})
        out.append(e)
    return out


def gdoc_action(body):
    eid, act = body.get("id", ""), body.get("act", "")
    with LOCK:
        st = load_state()
        it = st.get("gdoc", {}).get("shown", {}).get(eid)
        if not it:
            return {"ok": False, "msg": "找不到这一条"}
        cur = gdoc_status(st, it)
        if cur in DONE:
            return {"ok": False, "msg": f"这条已是「{cur}」"}
    if act == "tolead":
        if it["kind"] == "comment":
            q = f"Google 文档里有一条批注（{it.get('author') or 'Liang Hu'}）：「{it.get('comment', '')}」，请按批注给修改建议。"
        elif it["kind"] == "conflict":
            q = ("Google 文档和 Overleaf 两边都改了这段，Liang Hu 选「用 Google 文档的写法」。请对照 Overleaf 当前源码，"
                 f"按 Google 文档的写法给修改建议。Google 文档现写法：「{it.get('plain_new', '')[:1200]}」")
        else:
            q = f"Liang Hu 在 Google 文档里把选中原文改成了：「{it.get('plain_new', '')[:1200]}」。这处含 LaTeX 格式，请转成源码修改建议。"
        r = ask({"question": q, "selection": it.get("plain_old", "") or it.get("plain_new", ""), "page": None})
        if not r["ok"]:
            return r
        new = "已交 Lead"
    elif act == "ignore":
        new = "已忽略"
    elif act == "done":
        new = "已处理"
    else:
        return {"ok": False, "msg": "未知操作"}
    with LOCK:
        st = load_state()
        st["decisions"][eid] = {"status": new, "when": time.strftime("%m-%d %H:%M"),
                                "note": "保留 Overleaf 的写法" if (act == "ignore" and it["kind"] == "conflict") else ""}
        _gdoc_recompute(st)
        save_state(st)
    return {"ok": True, "msg": {"已交 Lead": "已发给 Lead，等它给出修改建议", "已忽略": "已记下，不写回",
                                "已处理": "已标为处理过"}[new]}


# ---------------- 定点同步到 Google 文档（11-15：接受写进 LaTeX 后，把同一句在 docx 里定点替换） ----------------
GSYNC_EVENT = threading.Event()
SYNC_DONE = ("已同步", "需重新确认", "不需要", "以文档为准", "暂未写进文档")
HOLD = "暂未写进文档"


def tex2plain(t, apos="’", nb="\u00a0"):
    t = " ".join(t.split())
    t = re.sub(r"\\(emph|textit|textbf|textsc|underline|textrm|mbox)\{([^{}]*)\}", r"\2", t)
    for a, b in (("\\ldots{}", "…"), ("\\ldots", "…"), ("---", "—"), ("--", "–"), ("``", "“"), ("''", "”"), ("`", "‘"),
                 ("\\%", "%"), ("\\&", "&"), ("\\_", "_")):
        t = t.replace(a, b)
    t = t.replace("'", apos).replace("~", nb)
    return t


def _gdoc_get(dst):
    src = gdoc_source()
    if src["kind"] == "file":
        shutil.copy(os.path.expanduser(src["path"]), dst)
        return True, ""
    rc, out = run([os.path.expanduser("~/bin/rc-gdoc"), "pull", src["path"], dst], timeout=120)
    return rc == 0 and os.path.exists(dst), out[-200:]


def _gdoc_native():
    if CFG.get("gdoc_native"):
        return True
    try:
        return bool(load_state().get("gdoc_native"))
    except Exception:
        return False


def _docx_has_notes(path):
    import zipfile as _z
    z = _z.ZipFile(path)
    n = z.namelist()
    com = z.read("word/comments.xml").decode("utf-8", "ignore").count("<w:comment ") if "word/comments.xml" in n else 0
    d = z.read("word/document.xml").decode("utf-8", "ignore")
    return com > 0 or "<w:ins " in d or "<w:del " in d


def _docs_client():
    import docs_api as _DA
    return _DA.Client(gdoc_source()["path"].rsplit(".docx", 1)[0] if CFG.get("docs_strip_ext", True) else gdoc_source()["path"])


def _same_docx(a, b):
    import zipfile as _z
    za, zb = _z.ZipFile(a), _z.ZipFile(b)
    return set(za.namelist()) == set(zb.namelist()) and all(za.read(n) == zb.read(n) for n in za.namelist())


def _gdoc_put(local):
    src = gdoc_source()
    if src["kind"] == "file":
        shutil.copy(local, os.path.expanduser(src["path"]))
        return True, ""
    folder, name = os.path.dirname(src["path"]), os.path.basename(src["path"])
    d = os.path.join(WS, "gsync_up_" + uuid.uuid4().hex[:6])
    os.makedirs(d)
    try:
        shutil.copy(local, os.path.join(d, name))
        rc, out = run([os.path.expanduser("~/bin/rc-gdoc"), "push", os.path.join(d, name), folder], timeout=180)
        if rc != 0 and "google document type" in out:  # 11-15 19:57 起该稿是原生 Google 文档：按 docx 导入、原地更新
            with LOCK:
                st = load_state(); st["gdoc_native"] = True; save_state(st)
            if _docx_has_notes(local):
                return False, "原生 Google 文档里有批注或建议，整篇导入会丢，未写回"
            rc, out = run([os.path.expanduser("~/bin/rc-gdoc"), "push-gdoc-docx", os.path.join(d, name), folder], timeout=240)
        return rc == 0, out[-200:]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def gsync_one(old_tex, new_tex):
    """在 Google 文档（Drive 里的 docx）里把 old 定点换成 new。返回 (状态, 说明)。只改这一句；原句找不到就不改。"""
    import zipfile as _z
    sys.path.insert(0, APP)
    from ooxml_suggest import Doc as _Doc
    native = _gdoc_native()
    if native and CFG.get("docs_api"):  # 11-16：原生 Google 文档用 Docs API 定点改，只改这一处，批注与建议保留
        import docs_api as _DA
        PAR = re.compile(r"\n[ \t]*\n")
        if len(PAR.split(old_tex.strip())) > 1:
            return "需重新确认", "原文跨了多个段落，不能自动同步到文档"
        variants = []
        for apos in ("’", "'"):
            for nb in ("\u00a0", " "):
                o = tex2plain(old_tex, apos, nb)
                n = "\n".join(tex2plain(x, apos, nb) for x in PAR.split(new_tex.strip()))
                if "\\" in o or "\\" in n or "{" in n:
                    return "需重新确认", "这句含 LaTeX 命令，不能自动换成文档文字"
                variants.append((o, n))
        try:
            return _DA.sync_one(_docs_client(), variants)
        except Exception as ex:
            return "失败", "定点写回出错：" + str(ex)[:150]
    tmpd = os.path.join(WS, "gsync_" + uuid.uuid4().hex[:6])
    os.makedirs(tmpd)
    try:
        for attempt in range(3):
            a = os.path.join(tmpd, "a.docx")
            ok, msg = _gdoc_get(a)
            if not ok:
                return "失败", "取 Google 文档失败：" + msg
            if native and _docx_has_notes(a):  # 定点写回没上线前：有批注/建议的原生文档不整篇导入，免得丢批注
                return HOLD, "这条暂未写进文档，避免丢批注（已进 LaTeX；定点写回上线后自动补上）"
            d = _Doc(a)
            done, why = False, ""
            # 11-16：建议里含「新增段」（空行分段）时，用分段记号整体替换后再切成新段落；原文本身跨段的仍交 Lead
            PAR = re.compile(r"\n[ \t]*\n")
            oparts, nparts = PAR.split(old_tex.strip()), PAR.split(new_tex.strip())
            for apos in ("’", "'"):
                for nb in ("\u00a0", " "):
                    if len(oparts) > 1:
                        why = "原文跨了多个段落，不能自动同步到文档"
                        continue
                    o = tex2plain(old_tex, apos, nb)
                    ns = [tex2plain(x, apos, nb) for x in nparts]
                    n = "\u2029".join(ns)
                    if "\\" in o or "\\" in n or "{" in n:
                        why = "这句含 LaTeX 命令，不能自动换成文档文字"
                        continue
                    if len(d.find(o)) == 1:
                        done, why = d.plain_replace(o, n)
                        if done and len(ns) > 1:
                            d.split_marks()
                            why += f"；新增 {len(ns) - 1} 段"
                        break
                    if all(len(d.find(x)) == 1 for x in ns if x.strip()) and not d.find(o):
                        return "已同步", "文档里已经是新写法"
                    why = "文档里找不到这句原文（可能你已在文档里改过）" if not d.find(o) else "文档里这句出现不止一处"
                if done:
                    break
            if not done:
                return "需重新确认", why
            b = os.path.join(tmpd, "b.docx")
            d.save(b)
            za, zb = _z.ZipFile(a), _z.ZipFile(b)
            for nm in za.namelist():
                if not re.match(r"word/(document|header\d*|footer\d*)\.xml$", nm) and za.read(nm) != zb.read(nm):
                    return "失败", f"核对没通过（{nm} 变了），未上传"
            # 上传前再取一次：若 Liang Hu 这几秒内又保存过，就在最新版本上重做，避免覆盖他的新文字
            c = os.path.join(tmpd, "c.docx")
            ok, msg = _gdoc_get(c)
            if ok and not _same_docx(a, c):  # 原生 Google 文档每次导出的 zip 字节都不同，按各部件内容比
                log("gsync: 文档刚被改过，在最新版本上重做")
                continue
            ok, msg = _gdoc_put(b)
            return ("已同步", why) if ok else ("失败", "上传失败：" + msg)
        return "失败", "文档一直在变（你可能正在连续输入），稍后自动重试"
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)


def gsync_pending(st):
    gs = st.setdefault("gsync", {})
    out = []
    for h in st.get("history", []):
        eid = h["id"]
        d = st["decisions"].get(eid, {})
        if d.get("status") != "已接受":
            continue
        if eid.startswith("g-"):
            if eid not in gs:
                gs[eid] = {"status": "不需要", "msg": "这条本来就是在 Google 文档里改的"}
            continue
        if gs.get(eid, {}).get("status") == HOLD and (CFG.get("docs_api") or not _gdoc_native()):
            out.append(h)  # 定点写回已上线（或文档不再是原生）→ 补写
            continue
        if gs.get(eid, {}).get("status") in SYNC_DONE:
            continue
        out.append(h)
    return out


def gsync_status(st):
    gs = st.get("gsync", {})
    acc = [h["id"] for h in st.get("history", []) if st["decisions"].get(h["id"], {}).get("status") == "已接受" and not h["id"].startswith("g-")]
    unsynced = sum(1 for i in acc if gs.get(i, {}).get("status") not in SYNC_DONE)
    recheck = sum(1 for i in acc if gs.get(i, {}).get("status") == "需重新确认")
    held = sum(1 for i in acc if gs.get(i, {}).get("status") == HOLD)
    last = max([v.get("when", "") for v in gs.values() if v.get("status") == "已同步"] or [""])
    return {"unsynced": unsynced, "recheck": recheck, "held": held, "last": last}


def gsync_run():
    if not gdoc_source() or CFG.get("gsync_disable"):
        return
    with GDOC_LOCK:
        with LOCK:
            todo = gsync_pending(load_state())
        for h in todo:
            stt, msg = gsync_one(h["old"], h["new"])
            with LOCK:
                st = load_state()
                gsync_pending(st)
                st.setdefault("gsync", {})[h["id"]] = {"status": stt, "msg": msg, "when": time.strftime("%m-%d %H:%M")}
                if stt == "已同步":
                    st["gsync"][h["id"]]["in_doc"] = True
                save_state(st)
            log(f"gsync {h['id'][:12]}: {stt} {msg[:120]}")
            if stt == "失败":
                break
    try:
        gdoc_refresh()
    except Exception as ex:
        log(f"gsync refresh: {ex}")


def gsync_loop():
    while True:
        GSYNC_EVENT.wait(timeout=int(CFG.get("gsync_interval", 90)))
        GSYNC_EVENT.clear()
        try:
            gsync_run()
        except Exception as ex:
            log(f"gsync loop error: {str(ex)[:200]}")


# ---------------- Google 文档为主稿：直接修改自动写进 LaTeX（11-15 Liang Hu 定） ----------------
import docsync as DSY  # noqa: E402
DSY.ACCEPT_TRACKED = CFG.get("accept_tracked", True)  # 11-16 Liang Hu：文档里的建议修订默认算已接受
MSYNC_EVENT = threading.Event()


def _commit_src(new_src, msg):
    """把整份 LaTeX 换成 new_src → 编译检查 → 提交推送；失败就还原。调用方持有 LOCK，且已确认目录干净并拉取过。"""
    path = os.path.join(REPO, MAIN)
    open(path, "w", encoding="utf-8").write(new_src)
    ok, cout, pdf = compile_to(os.path.join(WS, "build_check"))
    if not ok:
        git("checkout", "--", MAIN)
        return False, "编译不过，已回退：" + mask(cout.strip()[-200:])
    rc, prev = git("rev-parse", "HEAD")
    rc, out = run([DOCSYNC, REPO, msg], timeout=180)
    if rc != 0:
        git("reset", "--hard", prev.strip())
        return False, "推送失败，已回退：" + out[-200:]
    _, h = git("rev-parse", "--short", "HEAD")
    return True, h.strip()


def _added_frags(h):
    """已接受建议带来的新文字（新增或改写的词句，各带左右 3 个词作上下文，最多 80 字，归一化）。
    11-16 Liang Hu 定：这些文字若从没进过 Google 文档，就不能因「文档为主稿」从 LaTeX 删掉或改掉；须先补进文档（交 Lead）。"""
    A = DSY.norm(DSY.tex_plain(h["old"])).split()
    B = DSY.norm(DSY.tex_plain(h["new"])).split()
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes():
        if tag in ("insert", "replace") and j2 > j1:
            out.append(" ".join(B[max(0, j1 - 3):j2 + 3])[:80])
    return out


def _ever_in_doc(frags, baseline, dp):
    """这些文字是否在文档里出现过（上次同步的文档或当前文档）。"""
    pool = [DSY.norm(x) for x in baseline] + [DSY.norm(p["text"]) for p in dp]
    return bool(frags) and any(f in x for f in frags for x in pool)


def msync_run(manual=False):
    """一轮：先把已接受的 Lead 建议同步进文档（防循环），再把文档里的直接修改逐段写进 LaTeX。"""
    if not gdoc_source() or not CFG.get("doc_master", True):
        return {"ok": False, "msg": "未启用"}
    gsync_run()
    with LOCK:
        st = load_state()
        if gsync_status(st)["unsynced"] > 0:
            return {"ok": False, "msg": "还有已接受的建议在往 Google 文档同步，稍后再同步到 Overleaf"}
    with GDOC_LOCK:
        ok, msg = gdoc_fetch()
        if not ok:
            return {"ok": False, "msg": msg}
        with LOCK:
            st = load_state()
            ms = st.setdefault("msync", {"baseline": None, "issues": [], "log": []})
            clean, _ = ensure_clean()
            if not clean:
                return {"ok": False, "msg": "稿件目录有未提交改动，这轮跳过"}
            rc, out = pull()
            if rc != 0:
                return {"ok": False, "msg": "拉取 Overleaf 失败，这轮跳过"}
            dp = DSY.docx_body_paras(zipfile.ZipFile(GDOC_FILE).read("word/document.xml"))
            if ms.get("baseline") is None and CFG.get("msync_init_baseline"):  # 仅测试：以当前文档为「已同步」基线
                ms["baseline"] = [p["text"] for p in dp]
                ms["base_tex"] = DSY.tex_units_plain(open(os.path.join(REPO, MAIN), encoding="utf-8").read())
                save_state(st)
                return {"ok": True, "msg": "已建立基线", "n": 0}
            recheck_all = [h for h in st.get("history", []) if st.get("gsync", {}).get(h["id"], {}).get("status") == "需重新确认"]
            held = [h for h in st.get("history", []) if st.get("gsync", {}).get(h["id"], {}).get("status") == HOLD]
            # 11-16 规则：第 2 条（以文档为准）只适用于「进过文档、又被 Liang Hu 在文档里改掉」的；从没进过文档的 → 保护，不从 LaTeX 删，交 Lead 补进文档
            recheck, protect = [], []
            for h in recheck_all:
                added = _added_frags(h)
                if st["gsync"][h["id"]].get("in_doc") or _ever_in_doc(added, ms.get("baseline") or [], dp):
                    recheck.append(h)
                else:
                    protect += added
                    st["gsync"][h["id"]]["msg"] = "这条已接受，但还没进 Google 文档（文档里找不到原句）；LaTeX 保留不删，已交 Lead 补进文档"
            lead_frags = list(protect)
            for h in held:  # 暂未写进文档的（防丢批注）：内容只在 LaTeX，同样保护，不从 LaTeX 删
                protect += _added_frags(h)
            force = [DSY.norm(DSY.tex_plain(h["new"]))[:80] for h in recheck]
            done, issues, failed, touched, extra = [], [], set(), set(), []
            for _ in range(60):
                src = open(os.path.join(REPO, MAIN), encoding="utf-8").read()
                acts, iss = DSY.plan(src, dp, ms.get("baseline"), force=force, base_tex=ms.get("base_tex") or (),
                                     revert=[(h["new"], h["old"]) for h in recheck], protect=protect)
                acts = [a for a in acts if DSY.norm(a["doc"] or a.get("unit", {}).get("plain", "")) not in failed]
                issues = iss
                if not acts:
                    break
                a = acts[0]
                u = a.get("unit") or a.get("after")
                line = src[:u["a"]].count("\n") + 1 if u else 1
                key = DSY.norm(a["doc"] or u.get("plain", ""))
                if key in touched:  # 同一段在一轮里第二次要改 → 说明改动没收敛（11-15 同一句被插 13 遍），停下交 Lead
                    failed.add(key)
                    extra.append({"why": "这段同步一次后仍与文档不一致，已停下未再改（防重复插入）；请 Lead 按文档核对", "line": line, "doc": " ".join((a["doc"] or "")[:60].split())})
                    continue
                touched.add(key)
                when = time.strftime("%Y-%m-%d %H:%M")
                snippet = " ".join((a["doc"] or u.get("plain", ""))[:60].split())
                kind = {"word": "改", "replace": "改写", "insert": "新增段", "delete": "删段"}[a["kind"]]
                ok, info = _commit_src(DSY.apply(src, a), f"L26.25 工作台｜Liang Hu 在 Google 文档直接修改｜{kind} 第 {line} 行附近｜同步 {when}｜{snippet}")
                rec = {"when": when, "kind": kind, "line": line, "doc": snippet, "ok": ok, "info": info}
                ms["log"] = (ms.get("log", []) + [rec])[-200:]
                log(f"msync {kind} L{line}: {'提交 ' + info if ok else info}")
                if ok:
                    done.append(rec)
                else:
                    failed.add(DSY.norm(a["doc"] or u.get("plain", "")))
                    extra.append({"why": info, "line": line, "doc": snippet})
            issues = list(issues) + extra + [{"why": "已接受的 Lead 改动还没进 Google 文档（文档里找不到原句）；LaTeX 保留不删，请 Lead 补进文档", "line": None, "doc": f[:200]} for f in lead_frags]
            fails = set(failed)
            ms["baseline"] = [p["text"] for p in dp if DSY.norm(p["text"]) not in fails]
            ms["base_tex"] = DSY.tex_units_plain(open(os.path.join(REPO, MAIN), encoding="utf-8").read())
            ms["issues"] = [dict(i, when=time.strftime("%m-%d %H:%M")) for i in issues]
            ms["last"] = time.strftime("%m-%d %H:%M")
            ms["last_n"] = len(done)
            # 同步异常交 Lead：有新的才发，最多每小时一条；Liang Hu 不用处理
            keys = {(i.get("line"), i.get("doc", "")[:60]) for i in issues}
            old = {tuple(x) for x in ms.get("notified", [])}
            new = [i for i in issues if (i.get("line"), i.get("doc", "")[:60]) not in old]
            if new and CFG.get("chat") == "rc" and time.time() - ms.get("notified_t", 0) > 3600:
                body = "\n".join(f"- {('第 ' + str(i['line']) + ' 行附近：') if i.get('line') else ''}{i['why']}｜文档写法：{i.get('doc', '')[:200]}" for i in new[:10])
                rc_, out_ = chat_post("【稿件工作台·同步异常】（给 Lead：Google 文档是主稿，下面几处没能自动同步到 Overleaf，请直接把 LaTeX 改成与文档一致并提交，不用再问 Liang Hu；Liang Hu 无需处理）\n" + body)
                if rc_ == 0:
                    ms["notified"] = [list(k) for k in keys | old]
                    ms["notified_t"] = time.time()
            # 第 2 条：已按文档写法同步的「需重新确认」条目，改为「以文档为准」
            if not [i for i in issues if i.get("line")] or done:
                for h in recheck:
                    st["gsync"][h["id"]] = {"status": "以文档为准", "msg": "以 Liang Hu 在 Google 文档里的写法为准，已同步到 LaTeX", "when": time.strftime("%m-%d %H:%M")}
            save_state(st)
    if done:
        try:
            build_pdf_async()
        except Exception:
            pass
    gdoc_refresh()
    return {"ok": True, "msg": f"已同步到 Overleaf：{len(done)} 处" + (f"；{len(issues)} 处同步异常已交 Lead" if issues else ""), "n": len(done)}


def build_pdf_async():
    def _b():
        with LOCK:
            build_pdf()
    threading.Thread(target=_b, daemon=True).start()


def msync_loop():
    while True:
        MSYNC_EVENT.wait(timeout=int(CFG.get("msync_interval", 180)))
        MSYNC_EVENT.clear()
        try:
            msync_run()
        except Exception as ex:
            log(f"msync loop error: {str(ex)[:200]}")


def gdoc_loop():
    while True:
        try:
            gdoc_refresh()
        except Exception as ex:
            log(f"gdoc loop error: {ex}")
        time.sleep(int(CFG.get("gdoc_interval", 180)))


# ---------------- PDF 自动更新（11-15：原先只在启动无 PDF 或点「刷新」时编译，导致 PDF 过期） ----------------
META = os.path.join(WS, "build_meta.json")


def src_hash():
    import hashlib
    h = hashlib.sha1()
    for f in sorted(os.listdir(REPO)):
        if f == MAIN or f.endswith((".sty", ".cls", ".bib", ".bst")):
            try:
                h.update(f.encode() + open(os.path.join(REPO, f), "rb").read())
            except OSError:
                pass
    return h.hexdigest()[:12]


def load_meta():
    try:
        return json.load(open(META, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def build_pdf():
    """编译到临时目录，成功才替换 BUILD；记录对应的提交与编译时间（调用方持有 LOCK）。"""
    hsh = src_hash()
    _, c = git("log", "-1", "--format=%h|%ci", "--", MAIN)
    _, head = git("log", "-1", "--format=%h|%ci")
    clean, _ = ensure_clean()
    tmp = os.path.join(WS, "build_new")
    shutil.rmtree(tmp, ignore_errors=True)
    ok, cout, pdf = compile_to(tmp)
    m = load_meta()
    now = time.strftime("%m-%d %H:%M")
    if ok:
        for f in os.listdir(tmp):
            shutil.copy(os.path.join(tmp, f), os.path.join(BUILD, f))
        mc = (c.strip() or "|").split("|")
        hd = (head.strip() or "|").split("|")
        m = {"hash": hsh, "compiled_at": now, "main_commit": mc[0], "main_commit_time": mc[1][:16],
             "head": hd[0], "dirty": not clean, "error": "", "stamp": f"{hsh}-{int(time.time())}"}
    else:
        m.update({"error": "编译失败（" + now + "），仍显示上一次成功的 PDF：" + mask(cout.strip()[-200:]), "fail_hash": hsh})
    shutil.rmtree(tmp, ignore_errors=True)
    json.dump(m, open(META, "w", encoding="utf-8"), ensure_ascii=False)
    return ok, cout


def pdf_status():
    m = load_meta()
    cur = src_hash()
    return {"compiled_at": m.get("compiled_at"), "commit": m.get("main_commit"), "commit_time": m.get("main_commit_time"),
            "head": m.get("head"), "dirty": m.get("dirty"), "error": m.get("error", ""), "stamp": m.get("stamp", ""),
            "stale": bool(m) and m.get("hash") != cur}


def pdf_loop():
    while True:
        time.sleep(int(CFG.get("pdf_interval", 120)))
        try:
            with LOCK:
                clean, _ = ensure_clean()
                if clean:
                    pull()
                m = load_meta()
                cur = src_hash()
                if (m.get("hash") != cur or m.get("error")) and m.get("fail_hash") != cur:
                    build_pdf()
        except Exception as ex:
            log(f"pdf loop error: {ex}")


def refresh():
    with LOCK:
        rc, out = pull()
        ok, cout = build_pdf()
        _, h = git("log", "--oneline", "-1")
        if gdoc_source():
            threading.Thread(target=gdoc_refresh, daemon=True).start()
        return {"ok": rc == 0 and ok, "msg": ("已拉取并编译：" if ok else "编译失败：") + mask(h.strip() if ok else cout[-300:]),
                "pull": out.strip()[-200:]}


def accept_many(ids):
    """按顺序逐条接受（每条照常：先拉、唯一定位、编译检查、一条一提交）；只处理传入的条目。"""
    res = []
    for i in ids:
        r = accept(i)
        res.append({"id": i, "ok": r["ok"], "msg": r["msg"][:160]})
    ok = sum(1 for x in res if x["ok"])
    return {"ok": ok > 0, "msg": f"当前筛选的 {len(ids)} 条：写回 {ok} 条，未写回 {len(ids) - ok} 条（未写回的仍在列表里，原因见各条）", "results": res}


ASK_LOCK = threading.Lock()
RECENT_ASKS = {}  # key -> 时间；同一选区+同一问题 ASK_DEDUP_S 秒内只发一次（含正在发送中）
ASK_DEDUP_S = 60


def ask(body):
    sel = (body.get("selection") or "").strip()
    q = (body.get("question") or "").strip()
    page = body.get("page")
    if not q and not sel:
        return {"ok": False, "msg": "没有内容"}
    import hashlib
    key = hashlib.sha1((" ".join(sel.split()) + "|" + " ".join(q.split())).encode()).hexdigest()
    now = time.time()
    with ASK_LOCK:
        for k in [k for k, t in RECENT_ASKS.items() if now - t > ASK_DEDUP_S]:
            del RECENT_ASKS[k]
        if key in RECENT_ASKS:
            log(f"ask dedup: 同一提问 {now - RECENT_ASKS[key]:.1f}s 前已发，未重发 key={key[:8]}")
            return {"ok": True, "dup": True, "msg": "这条 60 秒内已发过，没有重发，等回复即可"}
        RECENT_ASKS[key] = now
    try:
        r = _ask(sel, q, page)
    except Exception:
        with ASK_LOCK:
            RECENT_ASKS.pop(key, None)
        raise
    if not r["ok"]:
        with ASK_LOCK:
            RECENT_ASKS.pop(key, None)  # 没发出去的允许重试
    return r


def _ask(sel, q, page):
    loc = locate(sel, page) if sel else None
    parts = ["【稿件工作台】" + (q or "这里请看一下")]
    if sel:
        where = f"PDF 第 {page} 页" + (f"；源文件 {loc['file']} 第 {loc['line']} 行附近" if loc else "；源文件位置未能自动定位")
        parts.append(f"\n选中原文（{where}）：\n> " + sel.replace("\n", " ")[:1500])
    parts.append("\n" + FORMAT_HINT)
    text = "\n".join(parts)
    rc, out = chat_post(text)
    st = load_state()
    st["asks"].append({"when": time.strftime("%m-%d %H:%M"), "page": page, "loc": loc, "ok": rc == 0, "q": q[:200], "sel": sel[:200]})
    save_state(st)
    return {"ok": rc == 0, "msg": "已发到对话" if rc == 0 else "没发出去：" + out, "loc": loc}


# ---------------- HTTP ----------------
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path).path
        if u in ("/", "/index.html"):
            return self.send(200, open(os.path.join(APP, "static", "index.html"), "rb").read(), "text/html; charset=utf-8")
        if u.startswith("/static/"):
            p = os.path.realpath(os.path.join(APP, u.lstrip("/")))
            if not p.startswith(os.path.join(APP, "static")) or not os.path.isfile(p):
                return self.send(404, {"msg": "not found"})
            ct = "text/javascript" if p.endswith((".mjs", ".js")) else "text/css" if p.endswith(".css") else "application/octet-stream"
            return self.send(200, open(p, "rb").read(), ct)
        if u == "/pdf":
            p = os.path.join(BUILD, os.path.splitext(MAIN)[0] + ".pdf")
            if not os.path.exists(p):
                return self.send(404, {"msg": "还没有编译出 PDF，点「刷新」"})
            return self.send(200, open(p, "rb").read(), "application/pdf")
        if u == "/api/state":
            st = load_state()
            try:
                msgs = chat_messages(40)
                err = ""
            except Exception as ex:  # 只读库暂时不可用
                msgs, err = [], str(ex)
            _, h = git("log", "--oneline", "-1")
            return self.send(200, {"title": CFG.get("title", ""), "mode": CFG.get("mode", ""), "head": h.strip(),
                                   "chat": msgs[-20:], "chat_error": err,
                                   **{k: v for k, v in private_view().items() if not k.startswith("_")},
                                   "gdoc": {k: st.get("gdoc", {}).get(k) for k in ("pending", "lag", "fetched", "msg")},
                                   "pdf": pdf_status(), **({"gsync": gsync_status(st), "msync": {k: st.get("msync", {}).get(k) for k in ("last", "last_n", "issues")}} if gdoc_source() else {}),
                                   "edits": pending_edits(chat_messages(200) if not err else [], st) + gdoc_view(st)})
        if u == "/api/gdoc_pending":
            st = load_state()
            return self.send(200, {"pending": st.get("gdoc", {}).get("pending", 0), "fetched": st.get("gdoc", {}).get("fetched")})
        return self.send(404, {"msg": "not found"})

    def do_POST(self):
        u = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            body = {}
        try:
            if u == "/api/refresh":
                return self.send(200, refresh())
            if u == "/api/ask":
                return self.send(200, ask(body))
            if u == "/api/accept":
                return self.send(200, accept(body.get("id", "")))
            if u == "/api/accept_many":
                return self.send(200, accept_many([str(x) for x in body.get("ids", [])][:100]))
            if u == "/api/reject":
                return self.send(200, reject(body.get("id", "")))
            if u == "/api/revert":
                return self.send(200, revert(body.get("id", "")))
            if u == "/api/msync_now":
                return self.send(200, msync_run(manual=True))
            if u == "/api/gdoc_refresh":
                return self.send(200, gdoc_refresh())
            if u == "/api/gdoc_action":
                return self.send(200, gdoc_action(body))
        except Exception as ex:
            log(f"error {u}: {ex}")
            return self.send(200, {"ok": False, "msg": "出错：" + mask(str(ex))[:300]})
        return self.send(404, {"msg": "not found"})


def main():
    servers = []
    for host in CFG["bind"]:
        s = ThreadingHTTPServer((host, int(CFG["port"])), H)
        servers.append(s)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        log(f"listening {host}:{CFG['port']} mode={CFG.get('mode')}")
    try:
        with LOCK:
            if load_meta().get("hash") != src_hash() or not os.path.exists(os.path.join(BUILD, os.path.splitext(MAIN)[0] + ".pdf")):
                build_pdf()
    except Exception as ex:
        log(f"initial build failed: {ex}")
    threading.Thread(target=pdf_loop, daemon=True).start()
    if gdoc_source():
        threading.Thread(target=gdoc_loop, daemon=True).start()
        threading.Thread(target=gsync_loop, daemon=True).start()
        threading.Thread(target=msync_loop, daemon=True).start()
        GSYNC_EVENT.set()  # 启动即补同步（含今天已接受、文档里还没有的条目）
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
