#!/usr/bin/env python3
"""L26.25 11-16 规则（Liang Hu 定）：已接受但还没进文档的内容，不能因「文档为主稿」从 LaTeX 删；删除只在文档里有过、后来没了时发生。
P1 复现 11-15：Liang Hu 先在文档改了原句 → Lead 新增段建议被接受（进不了文档）→ 同步后 LaTeX 仍保留新增段、记同步异常交 Lead、不标「以文档为准」。
P2 新增段建议被接受且文档原句没动 → 定点同步把新段作为独立段落插进文档；再同步到 Overleaf 无改动。
P3 正对照：P2 那段进过文档后 Liang Hu 在文档里删掉 → LaTeX 跟着删。"""
import json, os, re, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests_gdoc.py")).read().split("R = {}")[0])
from ooxml_suggest import Doc as _D, runs_of as _r  # noqa
FAKE = f"{WB}/fake_chat.jsonl"


def lead(e):
    with open(FAKE, "a") as f:
        f.write(json.dumps({"id": "a-" + uuid.uuid4().hex[:8], "role": "assistant", "ts": time.time(),
                            "content": "建议：\n```wb-edit\n" + json.dumps(e) + "\n```\n"}) + "\n")


def tex():
    return open(f"{REPO}/main.tex").read()


def ncommits():
    return int(sh("git --git-dir=../remote.git rev-list --count main").stdout.strip())


def dparas():
    return ["".join(t for _, t in _r(p)) for _, p in _D(DOCX).paragraphs()]


def accept_new(old, new):
    lead({"file": "main.tex", "old": old, "new": new, "why": "测试"})
    eid = [e["id"] for e in state()["edits"] if not e.get("source") and e["status"] == "待批"][-1]
    r = post("/api/accept", {"id": eid})
    t0 = time.time()
    while time.time() - t0 < 60 and (state().get("gsync") or {}).get("unsynced", 1) != 0:
        time.sleep(2)
    return eid, r


def gs(eid):
    return next(e for e in state()["edits"] if e["id"] == eid).get("gsync")


R = {}
post("/api/gdoc_refresh"); post("/api/msync_now")  # 建基线
# P1
direct("The coupled wake oscillator captures", "The coupled wake oscillator reproduces")
NEW1 = "Take the peak amplitude as an example. A twenty percent shortfall matters for fatigue design, so calibration comes first."
eid1, r1 = accept_new("The coupled wake oscillator captures the lock-in range but underestimates the peak amplitude.",
                      "The coupled wake oscillator captures the lock-in range but underestimates the peak amplitude.\n\n" + NEW1)
g1a = gs(eid1)
post("/api/gdoc_refresh"); m1 = post("/api/msync_now"); m1b = post("/api/msync_now")
t1 = tex(); iss = (state().get("msync") or {}).get("issues") or []
R["P1_未进文档的新增段不被删"] = {"accept": r1["msg"][:50], "gsync_after_accept": g1a, "msync": [m1["msg"], m1b["msg"]],
                           "LaTeX保留新增段": NEW1 in t1, "gsync_after_msync": gs(eid1),
                           "同步异常交Lead": [i["why"][:40] for i in iss if "还没进" in i["why"]][:2],
                           "pass": g1a == "需重新确认" and NEW1 in t1 and gs(eid1) != "以文档为准" and any("还没进" in i["why"] for i in iss)}
# P2
NEW2 = "This paragraph was added by the Lead as a separate paragraph for testing purposes only."
S2a, S2b = "and it's effect on the lock-in range.", "The remainder of this paper"
eid2, r2 = accept_new(S2a + " " + S2b, S2a + "\n\n" + NEW2 + "\n\n" + S2b)
D2 = dparas(); k = [i for i, t in enumerate(D2) if t == NEW2]
n2 = ncommits(); post("/api/gdoc_refresh"); m2 = post("/api/msync_now")
R["P2_新增段进文档成独立段"] = {"gsync": gs(eid2), "文档中独立成段": bool(k), "前一段结尾": D2[k[0] - 1][-50:] if k else None,
                          "msync": m2["msg"], "new_commits": ncommits() - n2, "LaTeX有": NEW2 in tex(),
                          "pass": gs(eid2) == "已同步" and len(k) == 1 and D2[k[0] - 1].endswith("effect on the lock-in range.") and D2[k[0] + 1].startswith(S2b) and NEW2 in tex()
                          and not any(NEW2[:30] in (i.get("doc") or "") for i in (state().get("msync") or {}).get("issues") or [])}
# P3
def drop(d):
    i = d.index(NEW2); a = d.rindex("<w:p>", 0, i) if "<w:p>" in d[:i] else d.rindex("<w:p ", 0, i); b = d.index("</w:p>", i) + 6
    return d[:a] + d[b:], None
edit_docx(drop)
n3 = ncommits(); post("/api/gdoc_refresh"); m3 = post("/api/msync_now")
R["P3_文档里删了才删"] = {"msync": m3["msg"], "issues": [(i.get("line"), i["why"][:50], (i.get("doc") or "")[:60]) for i in (state().get("msync") or {}).get("issues") or []], "new_commits": ncommits() - n3, "LaTeX已删": NEW2 not in tex(), "P1新增段仍在": NEW1 in tex(),
                     "pass": NEW2 not in tex() and NEW1 in tex() and ncommits() - n3 == 1}
print(json.dumps(R, ensure_ascii=False, indent=1))
