#!/usr/bin/env python3
"""L26.25 11-16 防丢批注暂缓：H1 原生文档有批注时接受一条 → 不写回文档（文档字节不变、批注仍在）、只进 LaTeX、页顶状态 held=1；
H2 再同步到 Overleaf 不会把这条从 LaTeX 删掉；H3 没有批注/建议的原生文档照常写回（对照）。"""
import json, os, sys, time, uuid, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests_gdoc.py")).read().split("R = {}")[0])
FAKE = f"{WB}/fake_chat.jsonl"


def lead(e):
    with open(FAKE, "a") as f:
        f.write(json.dumps({"id": "a-" + uuid.uuid4().hex[:8], "role": "assistant", "ts": time.time(),
                            "content": "建议：\n```wb-edit\n" + json.dumps(e) + "\n```\n"}) + "\n")


def accept(old, new):
    lead({"file": "main.tex", "old": old, "new": new, "why": "测试"})
    eid = [e["id"] for e in state()["edits"] if not e.get("source") and e["status"] == "待批"][-1]
    r = post("/api/accept", {"id": eid}); t0 = time.time()
    while time.time() - t0 < 60 and (state().get("gsync") or {}).get("unsynced", 1) != 0:
        time.sleep(2)
    return eid, r


def ncom():
    z = zipfile.ZipFile(DOCX); return z.read("word/comments.xml").decode().count("<w:comment ") if "word/comments.xml" in z.namelist() else 0


R = {}
post("/api/gdoc_refresh"); post("/api/msync_now")
comment("Wake oscillator models represent the fluctuating lift", "Liang Hu 的批注：这里要引原始文献吗？")
post("/api/gdoc_refresh"); post("/api/msync_now")
before = open(DOCX, "rb").read(); c0 = ncom()
eid, r = accept("The lock-in range extends from", "The lock-in range spans from")
g = next(e for e in state()["edits"] if e["id"] == eid)
GS = state().get("gsync") or {}
R["H1_有批注不写回"] = {"accept": r["msg"][:50], "gsync": g.get("gsync"), "gsync_msg": g.get("gsync_msg"), "doc_bytes_unchanged": open(DOCX, "rb").read() == before,
                    "comments_before_after": [c0, ncom()], "LaTeX有": "lock-in range spans from" in open(f"{REPO}/main.tex").read(), "held": GS.get("held"),
                    "pass": g.get("gsync") == "暂未写进文档" and open(DOCX, "rb").read() == before and c0 == ncom() == 1 and GS.get("held") == 1}
post("/api/gdoc_refresh"); m = post("/api/msync_now"); m2 = post("/api/msync_now")
R["H2_不从LaTeX删"] = {"msync": [m["msg"], m2["msg"]], "LaTeX仍有": "lock-in range spans from" in open(f"{REPO}/main.tex").read(),
                    "pass": "lock-in range spans from" in open(f"{REPO}/main.tex").read()}
print(json.dumps(R, ensure_ascii=False, indent=1))
