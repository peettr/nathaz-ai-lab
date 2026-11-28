#!/usr/bin/env python3
"""L26.25 定点同步到 Google 文档：G1 有未处理改动时接受一条；G2 定位不到不覆盖；G3 补同步（重启后）。输出 JSON。"""
import json, os, sys, time, uuid, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests_gdoc.py")).read().split("R = {}")[0])
from ooxml_suggest import Doc, runs_of  # noqa
FAKE = f"{WB}/fake_chat.jsonl"
PHASE = sys.argv[1] if len(sys.argv) > 1 else "a"


def lead(e):
    with open(FAKE, "a") as f:
        f.write(json.dumps({"id": "a-" + uuid.uuid4().hex[:8], "role": "assistant", "ts": time.time(),
                            "content": "建议：\n```wb-edit\n" + json.dumps(e) + "\n```\n"}) + "\n")


def gtext():
    d = Doc(DOCX); return " ".join("".join(t for _, t in runs_of(p)) for _, p in d.paragraphs())


def wait_sync(t=60):
    t0 = time.time()
    while time.time() - t0 < t:
        g = state().get("gsync", {})
        if g and g.get("unsynced") == 0:
            return g, round(time.time() - t0, 1)
        time.sleep(2)
    return state().get("gsync"), None


def gitems():
    return [e for e in state()["edits"] if e.get("source") == "gdoc" and e.get("live") and e["status"] not in ("已接受", "已忽略", "已处理", "已拒绝")]


R = {}
if PHASE == "a":
    post("/api/gdoc_refresh")
    direct("The coupled wake oscillator captures", "The coupled wake-oscillator model captures")       # Liang Hu 未处理改动 1
    direct("has been studied for decades", "has been studied extensively for decades")              # Liang Hu 未处理改动 2
    post("/api/gdoc_refresh")
    g_before = len(gitems())
    lead({"file": "main.tex", "old": "This test paper are used", "new": "This test paper is used", "why": "主谓一致"})
    eid = [e["id"] for e in state()["edits"] if not e.get("source") and e["status"] == "待批"][-1]
    r = post("/api/accept", {"id": eid}); g, dt = wait_sync()
    txt = gtext(); latex = open(f"{REPO}/main.tex").read()
    card = next(e for e in state()["edits"] if e["id"] == eid)
    R["G1_有未处理改动时接受一条"] = {"accept": r["msg"], "sync_seconds": dt, "gsync": g, "card_gsync": card.get("gsync"),
                                "文档出现修改": "This test paper is used" in txt, "Liang Hu改动1仍在": "wake-oscillator model captures" in txt,
                                "Liang Hu改动2仍在": "studied extensively for decades" in txt, "LaTeX已写": "This test paper is used" in latex,
                                "Google文档未处理条目_前后": [g_before, len(gitems())]}
    R["G1_有未处理改动时接受一条"]["pass"] = all(R["G1_有未处理改动时接受一条"][k] for k in ("文档出现修改", "Liang Hu改动1仍在", "Liang Hu改动2仍在", "LaTeX已写")) and g_before == len(gitems()) == 2 and card.get("gsync") == "已同步"
    # G2 Liang Hu 已在文档里改过这句 → 不替换，标需重新确认
    direct("We considers a wake oscillator", "We now consider a wake-oscillator")
    post("/api/gdoc_refresh")
    lead({"file": "main.tex", "old": "We considers a wake oscillator", "new": "We consider a wake oscillator", "why": "主谓一致"})
    eid2 = [e["id"] for e in state()["edits"] if not e.get("source") and e["status"] == "待批"][-1]
    r2 = post("/api/accept", {"id": eid2}); g2, dt2 = wait_sync()
    txt = gtext(); card2 = next(e for e in state()["edits"] if e["id"] == eid2)
    R["G2_定位不到不覆盖"] = {"accept": r2["msg"], "card_gsync": card2.get("gsync"), "msg": card2.get("gsync_msg"), "gsync": g2,
                          "Liang Hu的写法保留": "We now consider a wake-oscillator" in txt, "未被LaTeX写法覆盖": "We consider a wake oscillator coupled" not in txt}
    R["G2_定位不到不覆盖"]["pass"] = card2.get("gsync") == "需重新确认" and R["G2_定位不到不覆盖"]["Liang Hu的写法保留"] and R["G2_定位不到不覆盖"]["未被LaTeX写法覆盖"]
    print(json.dumps(R, ensure_ascii=False, indent=1))
elif PHASE == "b1":  # 同步关闭时接受一条（模拟「今天已接受、文档里还没有」）
    post("/api/gdoc_refresh")
    lead({"file": "main.tex", "old": "coupled to a elastically mounted", "new": "coupled to an elastically mounted", "why": "冠词"})
    eid = [e["id"] for e in state()["edits"] if not e.get("source") and e["status"] == "待批"][-1]
    r = post("/api/accept", {"id": eid}); time.sleep(3)
    print(json.dumps({"accept": r["msg"], "文档里还没有": "coupled to an elastically" not in gtext()}, ensure_ascii=False))
else:  # b2：开同步重启后自动补上
    g, dt = wait_sync()
    print(json.dumps({"G3_补同步": {"gsync": g, "seconds": dt, "文档已补上": "coupled to an elastically" in gtext(), "pass": dt is not None and "coupled to an elastically" in gtext()}}, ensure_ascii=False))
