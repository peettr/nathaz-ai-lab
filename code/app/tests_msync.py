#!/usr/bin/env python3
"""L26.25 Google 文档为主稿：M1 直接修改自动进 LaTeX；M2 建议修订默认接受（11-16 改）；M3 接受 Lead 建议不循环回写；M4 含公式→同步异常；M6 先接受后被改写→未进过文档的不删、交 Lead（11-16 改）。
用法：tests_msync.py [auto]   （auto：只测定时自动同步 M5）"""
import json, os, re, subprocess, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests_gdoc.py")).read().split("R = {}")[0])
FAKE = f"{WB}/fake_chat.jsonl"


def lead(e):
    with open(FAKE, "a") as f:
        f.write(json.dumps({"id": "a-" + uuid.uuid4().hex[:8], "role": "assistant", "ts": time.time(),
                            "content": "建议：\n```wb-edit\n" + json.dumps(e) + "\n```\n"}) + "\n")


def tex():
    return open(f"{REPO}/main.tex").read()


def ncommits():
    return int(sh("git --git-dir=../remote.git rev-list --count main").stdout.strip())


def msgs(n):
    return sh(f"git --git-dir=../remote.git log -{n} --format=%s main").stdout.strip().split("\n")


def gpend():
    return [e for e in state()["edits"] if e.get("source") == "gdoc" and e.get("live") and e["status"] in ("待批", "需 Lead 转写", "冲突待定", "批注")]


def wait_gsync(t=60):
    t0 = time.time()
    while time.time() - t0 < t:
        g = state().get("gsync") or {}
        if g.get("unsynced") == 0:
            return True
        time.sleep(2)
    return False


R = {}
if len(sys.argv) > 1 and sys.argv[1] == "auto":
    post("/api/gdoc_refresh")
    time.sleep(12)  # 等第一轮自动同步建好基线
    direct("The coupled wake oscillator captures", "The coupled wake-oscillator model captures")
    t0 = time.time(); ok = False
    while time.time() - t0 < 90:
        if "wake-oscillator model captures" in sh("git --git-dir=../remote.git show main:main.tex").stdout:
            ok = True; break
        time.sleep(3)
    R["M5_定时自动同步"] = {"seconds": round(time.time() - t0, 1) if ok else None, "commit_msg": msgs(1)[0][:80], "pass": ok and "Liang Hu 在 Google 文档直接修改" in msgs(1)[0]}
    print(json.dumps(R, ensure_ascii=False, indent=1)); sys.exit()

post("/api/gdoc_refresh"); r0 = post("/api/msync_now")  # 建基线（测试稿由 pandoc 生成，换算差异不当作修改）
# M1 三处直接修改：结论段、含引用的引言段、小节标题
n0 = ncommits()
direct("The coupled wake oscillator captures", "The coupled wake-oscillator model captures")
direct("has been studied for decades", "has been studied extensively for decades")
direct(">Results<", ">Results and discussion<")
r1 = post("/api/msync_now"); t = tex()
post("/api/refresh"); time.sleep(4); P = state()["pdf"]
R["M1_直接修改自动进LaTeX"] = {"msync": r1["msg"], "new_commits": ncommits() - n0, "commit_msgs": [m[:70] for m in msgs(ncommits() - n0)],
                           "结论段": "wake-oscillator model captures" in t, "含引用段（\\citep 保留）": "studied extensively for decades \\citep{williamson2004}" in t,
                           "小节标题": "\\section{Results and discussion}" in t, "编译": {"error": P.get("error"), "commit": P.get("commit")}, "待批里没有这些": len(gpend())}
R["M1_直接修改自动进LaTeX"]["pass"] = (ncommits() - n0 == 3 and all(R["M1_直接修改自动进LaTeX"][k] for k in ("结论段", "含引用段（\\citep 保留）", "小节标题"))
                                    and not P.get("error") and len(gpend()) == 0 and all("Liang Hu 在 Google 文档直接修改" in m for m in msgs(3)))
# M2（11-16 改）Liang Hu 用建议模式（修订）改 → 默认算已接受：自动写进 LaTeX、不进待批，文档里修订痕迹保留
tracked("lock-in range but underestimates the peak amplitude", "underestimates", "underpredicts")
n1 = ncommits(); post("/api/gdoc_refresh"); r2 = post("/api/msync_now")
gp = gpend(); dx = zipfile.ZipFile(DOCX).read("word/document.xml").decode()
R["M2_建议修订默认接受"] = {"msync": r2["msg"], "new_commits": ncommits() - n1, "pending": [(e["kind"], e.get("origin")) for e in gp],
                         "LaTeX已按接受改": "underpredicts the peak" in tex(), "文档修订痕迹仍在": "<w:ins " in dx and "<w:del " in dx,
                         "pass": ncommits() == n1 + 1 and len(gp) == 0 and "underpredicts the peak" in tex() and "<w:ins " in dx}
# M2b Liang Hu 在文档里拒绝了自己的这条修订 → 文档文字回到原样 → LaTeX 跟着回去
def _reject(d):
    d = re.sub(r'<w:ins w:id="902"[^>]*>.*?</w:ins>', "", d, flags=re.S)
    d = re.sub(r'<w:del w:id="901"[^>]*><w:r><w:delText>(.*?)</w:delText></w:r></w:del>', r'<w:r><w:t xml:space="preserve">\1</w:t></w:r>', d, flags=re.S)
    return d, None
edit_docx(_reject)
n2b = ncommits(); post("/api/gdoc_refresh"); r2b = post("/api/msync_now")
R["M2b_拒绝修订LaTeX跟回"] = {"msync": r2b["msg"], "new_commits": ncommits() - n2b, "LaTeX回到原文": "underestimates the peak" in tex() and "underpredicts" not in tex(),
                           "pass": ncommits() == n2b + 1 and "underestimates the peak" in tex() and "underpredicts" not in tex()}
# M2c Lead 写进文档的修订不算 Liang Hu 接受 → 不自动进 LaTeX
def _lead_tracked(d):
    a = "studied extensively for decades"
    assert a in d
    pre, post_ = a.split("for decades", 1)
    mark = (f'{pre}</w:t></w:r><w:del w:id="911" w:author="Lead"><w:r><w:delText>for decades</w:delText></w:r></w:del>'
            f'<w:ins w:id="912" w:author="Lead"><w:r><w:t>for many decades</w:t></w:r></w:ins><w:r><w:t xml:space="preserve">{post_}')
    return d.replace(a, mark, 1), None
edit_docx(_lead_tracked)
n2c = ncommits(); post("/api/gdoc_refresh"); r2c = post("/api/msync_now")
R["M2c_Lead修订不自动接受"] = {"msync": r2c["msg"], "new_commits": ncommits() - n2c, "LaTeX未改": "for many decades" not in tex(),
                             "pass": ncommits() == n2c and "for many decades" not in tex()}
# M3 接受 Lead 建议 → 同步进文档 → 再同步到 Overleaf 不回写
lead({"file": "main.tex", "old": "The lock-in range extends from", "new": "The lock-in range spans from", "why": "用词"})
eid = [e["id"] for e in state()["edits"] if not e.get("source") and e["status"] == "待批"][-1]
ra = post("/api/accept", {"id": eid}); wait_gsync()
n2 = ncommits(); r3 = post("/api/msync_now"); r3b = post("/api/msync_now")
from ooxml_suggest import Doc as _D, runs_of as _r
d3 = " ".join("".join(t for _, t in _r(p)) for _, p in _D(DOCX).paragraphs()).encode()
R["M3_接受Lead建议不循环"] = {"accept": ra["msg"][:60], "doc_has_lead_edit": b"range spans from" in d3, "msync": [r3["msg"], r3b["msg"]],
                           "new_commits_after_accept": ncommits() - n2, "issues": (state().get("msync") or {}).get("issues"),
                           "pass": b"range spans from" in d3 and ncommits() == n2 and "range spans from" in tex()}
# M4 含公式段的直接修改 → 同步异常，不进待批、不提交
direct("is the Strouhal frequency,", "denotes the Strouhal frequency,")
n3 = ncommits(); post("/api/gdoc_refresh"); r4 = post("/api/msync_now")
iss = (state().get("msync") or {}).get("issues") or []
R["M4_含公式段记同步异常"] = {"msync": r4["msg"], "new_commits": ncommits() - n3, "issues": [(i.get("line"), i["why"][:40]) for i in iss], "pending": len(gpend()),
                           "pass": (ncommits() == n3 or "denotes the Strouhal" in tex()) and len(gpend()) == 0}
# M6 Liang Hu 先在文档改了一句，Lead 对原句的建议被接受 → 文档里找不到（需重新确认）→ 同步到 Overleaf 时以文档写法为准
direct("we revisit the coupling term", "we re-examine the coupling term")
lead({"file": "main.tex", "old": "we revisit the coupling term", "new": "we reconsider the coupling term", "why": "用词"})
eid6 = [e["id"] for e in state()["edits"] if not e.get("source") and e["status"] == "待批"][-1]
r6a = post("/api/accept", {"id": eid6}); wait_gsync()
g6 = next(e for e in state()["edits"] if e["id"] == eid6).get("gsync")
r6 = post("/api/msync_now"); t6 = tex()
g6b = next(e for e in state()["edits"] if e["id"] == eid6).get("gsync")
iss6 = (state().get("msync") or {}).get("issues") or []
# 11-16 Liang Hu 定：已接受但从没进过文档的改动不从 LaTeX 删/改 → 保留 Lead 写法、记同步异常交 Lead 补进文档（原「以文档为准」只适用于进过文档的）
R["M6_先接受后被改写_不删交Lead"] = {"after_accept_gsync": g6, "msync": r6["msg"], "LaTeX保留已接受写法": "we reconsider the coupling term" in t6, "after_gsync": g6b,
                                "issue": [i["why"][:40] for i in iss6 if "还没进" in i["why"]][:1],
                                "pass": g6 == "需重新确认" and "we reconsider the coupling term" in t6 and g6b == "需重新确认" and any("还没进" in i["why"] for i in iss6)}
print(json.dumps(R, ensure_ascii=False, indent=1))
