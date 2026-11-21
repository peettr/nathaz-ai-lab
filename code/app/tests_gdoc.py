#!/usr/bin/env python3
"""L26.25 第二步测试 T6–T11（测试副本：~/l26_25_ws/repo＋假远端；Google 文档用本地 docx 模拟 Liang Hu 的改动）。输出 JSON。"""
import json, os, re, subprocess, time, urllib.request, uuid, zipfile

B = "http://127.0.0.1:8766"
WS = os.path.expanduser("~/l26_25_ws")
GT = f"{WS}/gdoc_test"
DOCX = f"{GT}/peter.docx"
REPO = f"{WS}/repo"
WB = f"{WS}/wb_gdoc"


def post(u, b=None, timeout=300):
    r = urllib.request.Request(B + u, data=json.dumps(b or {}).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read())


def state():
    return json.loads(urllib.request.urlopen(B + "/api/state", timeout=60).read())


def sh(cmd, cwd=REPO):
    return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)


def edit_docx(fn):
    z = zipfile.ZipFile(DOCX)
    files = {n: z.read(n) for n in z.namelist()}
    z.close()
    d = files["word/document.xml"].decode()
    d, extra = fn(d)
    files["word/document.xml"] = d.encode()
    files.update(extra or {})
    tmp = DOCX + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as o:
        for n, b in files.items():
            o.writestr(n, b)
    os.replace(tmp, DOCX)


def direct(a, b):
    def f(d):
        assert a in d, a
        return d.replace(a, b, 1), None
    edit_docx(f)


def tracked(a, old, new):
    """把 w:t 里的 a 中的 old 换成「删除 old＋插入 new」的建议修订标记。"""
    def f(d):
        assert a in d, a
        pre, post_ = a.split(old, 1)
        mark = (f'{pre}</w:t></w:r><w:del w:id="901" w:author="Liang Hu"><w:r><w:delText>{old}</w:delText></w:r></w:del>'
                f'<w:ins w:id="902" w:author="Liang Hu"><w:r><w:t>{new}</w:t></w:r></w:ins><w:r><w:t xml:space="preserve">{post_}')
        return d.replace(a, mark, 1), None
    edit_docx(f)


def comment(a, text):
    def f(d):
        assert a in d, a
        pre, post_ = d.split(a, 1)
        # a 所在 run 前后插锚点（简化：锚在文字两侧）
        d2 = pre + f'</w:t></w:r><w:commentRangeStart w:id="7"/><w:r><w:t xml:space="preserve">{a}</w:t></w:r><w:commentRangeEnd w:id="7"/><w:r><w:t xml:space="preserve">' + post_
        cx = (f'<?xml version="1.0" encoding="UTF-8"?><w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
              f'<w:comment w:id="7" w:author="Liang Hu"><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:comment></w:comments>')
        return d2, {"word/comments.xml": cx.encode()}
    edit_docx(f)


def gitems():
    return [e for e in state()["edits"] if e.get("source") == "gdoc"]


def pending():
    return json.loads(urllib.request.urlopen(B + "/api/gdoc_pending").read())["pending"]


def pending_file():
    return json.load(open(f"{WB}/gdoc_pending.json"))["pending"]


def live(kind=None, status=None):
    return [e for e in gitems() if e.get("live") and (kind is None or e["kind"] == kind) and (status is None or e["status"] == status)]


R = {}
r0 = post("/api/gdoc_refresh")
R["T6_0_初始"] = {"msg": r0["msg"], "items": len(gitems()), "pending": pending(), "pass": r0["ok"] and len(gitems()) == 0 and pending() == 0}

# T6 直接改 → 待批 → 接受写回
direct("The coupled wake oscillator captures", "The coupled wake-oscillator model captures")
post("/api/gdoc_refresh")
e = live("edit", "待批")
p_before, pf_before = pending(), pending_file()
h0 = sh("git rev-parse HEAD").stdout.strip()
ra = post("/api/accept", {"id": e[0]["id"]}) if e else {"ok": False, "msg": "无待批"}
txt = open(f"{REPO}/main.tex").read()
msg = sh("git log -1 --format=%s").stdout.strip()
diff_files = sh(f"git diff --name-only {h0} HEAD").stdout.split()
R["T6_直接改"] = {"item": (e[0]["old"], e[0]["new"]) if e else None, "pending_before": p_before, "pending_file_before": pf_before,
                 "accept": ra["msg"], "commit_msg": msg, "latex_has_new": "The coupled wake-oscillator model captures" in txt,
                 "only_main": diff_files == ["main.tex"], "pending_after": pending(),
                 "remote_head": sh("git --git-dir=../remote.git log -1 --format=%s main").stdout.strip()[:60]}
R["T6_直接改"]["pass"] = bool(e) and ra["ok"] and "Google 文档改动" in msg and R["T6_直接改"]["latex_has_new"] and p_before == 1 and pf_before == 1 and pending() == 0

# T6b 建议修订 → 待批 → 接受
tracked("This test paper are used to evaluate an editing tool.", "evaluate", "test")
post("/api/gdoc_refresh")
e = live("edit", "待批")
ra = post("/api/accept", {"id": e[0]["id"]}) if e else {"ok": False, "msg": "无待批"}
txt = open(f"{REPO}/main.tex").read()
R["T6b_建议修订"] = {"item": (e[0]["old"], e[0]["new"], e[0].get("origin")) if e else None, "accept": ra["msg"],
                    "latex_has_new": "used to test an editing tool" in txt, "pending_after": pending()}
R["T6b_建议修订"]["pass"] = bool(e) and ra["ok"] and R["T6b_建议修订"]["latex_has_new"] and pending() == 0

# T9 批注 → 列出 → 标已处理
comment("Future work will calibrate", "能否更具体？")
post("/api/gdoc_refresh")
c = live("comment")
p1 = pending()
rc_ = post("/api/gdoc_action", {"id": c[0]["id"], "act": "done"}) if c else {"ok": False}
R["T9_批注"] = {"item": (c[0]["plain_old"], c[0]["comment"], c[0].get("line")) if c else None, "pending_before": p1,
               "act": rc_.get("msg"), "pending_after": pending(), "pass": bool(c) and p1 == 1 and rc_["ok"] and pending() == 0}

# T10 含公式处 → 需 Lead 转写 → 交 Lead → Lead 给 wb-edit → 接受 → 清零
direct("is the Strouhal frequency,", "denotes the Strouhal frequency,")
post("/api/gdoc_refresh")
n = live("need_lead")
fake = f"{WB}/fake_chat.jsonl"
before = sum(1 for _ in open(fake)) if os.path.exists(fake) else 0
rt = post("/api/gdoc_action", {"id": n[0]["id"], "act": "tolead"}) if n else {"ok": False}
after = [json.loads(l) for l in open(fake)][before:] if os.path.exists(fake) else []
p_mid = pending()
with open(fake, "a") as f:
    wb = {"file": "main.tex", "old": "$ is the Strouhal frequency", "new": "$ denotes the Strouhal frequency", "why": "按 Google 文档"}
    f.write(json.dumps({"id": "a-" + uuid.uuid4().hex[:8], "role": "assistant", "ts": time.time(),
                        "content": "按 Google 文档改：\n```wb-edit\n" + json.dumps(wb) + "\n```\n"}) + "\n")
lid = [x["id"] for x in state()["edits"] if x.get("source") != "gdoc" and x["status"] == "待批"][-1]
rl = post("/api/accept", {"id": lid})
post("/api/gdoc_refresh")
R["T10_需Lead转写"] = {"item": (n[0]["plain_old"], n[0]["plain_new"]) if n else None, "tolead": rt.get("msg"),
                      "posted_to_chat": sum(1 for m in after if m["role"] == "user" and "【稿件工作台】" in m["content"]),
                      "pending_while_waiting": p_mid, "lead_edit_accept": rl["msg"], "pending_after": pending()}
R["T10_需Lead转写"]["pass"] = bool(n) and rt.get("ok") and R["T10_需Lead转写"]["posted_to_chat"] == 1 and p_mid == 1 and rl["ok"] and pending() == 0

# T7 冲突：同一段 Google 文档与 Overleaf 都改 → 列冲突、不能接受 → 选用 Overleaf 的
tmp = f"{WS}/collab"
subprocess.run(f"rm -rf {tmp} && git clone -q {WS}/remote.git {tmp}", shell=True)
sh("sed -i 's/has been studied for decades/has been investigated for decades/' main.tex && "
   "git -c user.name=c -c user.email=c@c commit -qam collab-conflict && git push -q origin main", cwd=tmp)
direct("has been studied for decades", "has been studied extensively for decades")
post("/api/refresh")
post("/api/gdoc_refresh")
k = live("conflict")
pk = pending()
rk = post("/api/accept", {"id": k[0]["id"]}) if k else {"ok": True}
ri = post("/api/gdoc_action", {"id": k[0]["id"], "act": "ignore"}) if k else {"ok": False}
txt = open(f"{REPO}/main.tex").read()
R["T7_冲突"] = {"item": (k[0]["plain_old"][:80], k[0]["plain_new"][:80], k[0]["why"]) if k else None, "pending": pk,
               "accept_refused": not rk["ok"], "accept_msg": rk.get("msg"), "choose_overleaf": ri.get("msg"),
               "latex_kept_overleaf": "has been investigated for decades" in txt, "pending_after": pending()}
R["T7_冲突"]["pass"] = bool(k) and pk == 1 and not rk["ok"] and ri["ok"] and R["T7_冲突"]["latex_kept_overleaf"] and pending() == 0

# T11 只有 Overleaf 改 → 不算待批，显示 Google 文档落后
sh("sed -i 's/shows the amplitude response/presents the amplitude response/' main.tex && "
   "git -c user.name=c -c user.email=c@c commit -qam collab-only && git push -q origin main", cwd=tmp)
post("/api/refresh")
post("/api/gdoc_refresh")
g = state()["gdoc"]
R["T11_仅Overleaf改"] = {"lag": g.get("lag"), "new_items": len([e for e in live() if e["status"] in ("待批", "冲突待定", "需 Lead 转写", "批注")]),
                        "pending": pending(), "pass": (g.get("lag") or 0) >= 1 and pending() == 0}

# T8 未处理提醒：有一条未处理时 pending 文件=1，处理后=0（贯穿上面各步，这里汇总）
R["T8_未处理不重新生成"] = {"seen_pending_1_then_0": [R["T6_直接改"]["pending_file_before"], pending_file()],
                          "pass": R["T6_直接改"]["pending_file_before"] == 1 and pending_file() == 0}
logs = open(f"{WB}/workbench.log", encoding="utf-8").read()
R["T5_令牌"] = {"olp_plain_hits": len(re.findall(r"olp_[A-Za-z0-9]{6,}", logs)), "pass": not re.findall(r"olp_[A-Za-z0-9]{6,}", logs)}
print(json.dumps(R, ensure_ascii=False, indent=1))
