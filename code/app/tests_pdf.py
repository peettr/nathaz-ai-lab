#!/usr/bin/env python3
"""L26.25 T12–T13：PDF 自动更新与编译失败处理（测试副本，pdf_interval=5 s）。输出 JSON。"""
import json, os, subprocess, time, urllib.request
B = "http://127.0.0.1:8766"; WS = os.path.expanduser("~/l26_25_ws"); REPO = f"{WS}/repo"; WB = f"{WS}/wb_pdf"
def st(): return json.loads(urllib.request.urlopen(B + "/api/state", timeout=60).read())
def sh(c, cwd): return subprocess.run(c, cwd=cwd, shell=True, capture_output=True, text=True)
def pdftext(): return sh(f"pdftotext {WB}/build/main.pdf -", WS).stdout
def wait(cond, t=60):
    t0 = time.time()
    while time.time() - t0 < t:
        s = st()
        if cond(s): return s, round(time.time() - t0, 1)
        time.sleep(2)
    return st(), None
R = {}
s0 = st()["pdf"]
tmp = f"{WS}/collab"; subprocess.run(f"rm -rf {tmp} && git clone -q {WS}/remote.git {tmp}", shell=True)
# T12 有人在 Overleaf（远端）改了正文 → 工作台自动拉取并重编，页面拿到新 stamp、提交号对得上
sh("sed -i 's/The coupled wake oscillator captures/The coupled wake oscillator reproduces/' main.tex && git -c user.name=c -c user.email=c@c commit -qam remote-edit && git push -q origin main", tmp)
rh = sh("git log -1 --format=%h", tmp).stdout.strip()
s, dt = wait(lambda s: s["pdf"].get("commit") == rh and not s["pdf"]["stale"])
R["T12_远端改动自动更新PDF"] = {"before": {k: s0.get(k) for k in ("compiled_at", "commit")}, "after": {k: s["pdf"].get(k) for k in ("compiled_at", "commit", "stale", "error")},
                          "remote_head": rh, "seconds": dt, "pdf_has_new_text": "reproduces" in pdftext(), "stamp_changed": s["pdf"]["stamp"] != s0.get("stamp")}
R["T12_远端改动自动更新PDF"]["pass"] = dt is not None and R["T12_远端改动自动更新PDF"]["pdf_has_new_text"] and R["T12_远端改动自动更新PDF"]["stamp_changed"]
# T13 远端推了编译不过的改动 → 保留上一份 PDF，页面显示编译失败；修好后恢复
good = st()["pdf"]
sh("sed -i 's/\\\\end{abstract}/\\\\end{abstrakt}/' main.tex && git -c user.name=c -c user.email=c@c commit -qam broken && git push -q origin main", tmp)
s, dt = wait(lambda s: bool(s["pdf"].get("error")))
kept = "reproduces" in pdftext()
R["T13_编译失败保留旧PDF"] = {"error_shown": (s["pdf"].get("error") or "")[:80], "seconds": dt, "old_pdf_kept": kept, "stale_flag": s["pdf"]["stale"]}
sh("sed -i 's/\\\\end{abstrakt}/\\\\end{abstract}/' main.tex && git -c user.name=c -c user.email=c@c commit -qam fixed && git push -q origin main", tmp)
rh2 = sh("git log -1 --format=%h", tmp).stdout.strip()
s, dt2 = wait(lambda s: not s["pdf"].get("error") and not s["pdf"]["stale"] and s["pdf"].get("head") == rh2)
R["T13_编译失败保留旧PDF"].update({"recovered_seconds": dt2, "after_fix": {k: s["pdf"].get(k) for k in ("compiled_at", "commit", "error")}})
R["T13_编译失败保留旧PDF"]["pass"] = dt is not None and kept and s0 is not None and dt2 is not None
print(json.dumps(R, ensure_ascii=False, indent=1))
