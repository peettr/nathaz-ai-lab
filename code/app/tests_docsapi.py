#!/usr/bin/env python3
"""L26.25 11-16 定点写回（Docs API 请求）单元测试：D1 改词只动那几个字、别处批注锚点不动；D2 新增段＝插入换行成独立段；
D3 批注所在句被改时批注仍在（锚点收缩/平移，不删除批注）；D4 修订号不符→在最新版本上重做；D5 句上有未处理建议→不改交 Lead。"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docs_api as DA

P = ["Thrust 2. Reviewing the field", "I will review the main research directions of the past fifteen years. (vi) what each tool is fit for in practice.",
     "The products are benchmarks that show how far each tool reproduces measurements.", "Thrust 3. Verification"]
def mk():
    m = DA.MockClient(P, [])
    t = m.text
    def cm(cid, q):
        i = t.index(q) + 1
        return {"id": cid, "start": i, "end": i + len(q), "quote": q}
    m.comments = [cm("c1", "past fifteen years"), cm("c2", "benchmarks that show"), cm("c3", "Verification")]
    return m

R = {}
m = mk()
st, msg = DA.sync_one(m, [("how far each tool reproduces", "how far each computational tool reproduces")])
R["D1_改词只动一处"] = {"status": st, "msg": msg, "text_ok": "how far each computational tool reproduces measurements." in m.text,
                    "comments": {c["id"]: m.quote(c) for c in m.comments},
                    "pass": st == "已同步" and m.text == mk().text.replace("each tool reproduces", "each computational tool reproduces")
                    and [m.quote(c) for c in m.comments] == ["past fifteen years", "benchmarks that show", "Verification"]}
m = mk()
st, msg = DA.sync_one(m, [("(vi) what each tool is fit for in practice.", "(vi) what each tool is fit for in practice.\nTake (vi) as an example. Design peak pressures still rest on wind-tunnel tests.")])
paras = m.text.split("\n")
R["D2_新增段成独立段"] = {"status": st, "msg": msg, "paras": paras[1:4],
                      "pass": st == "已同步" and paras[2] == "Take (vi) as an example. Design peak pressures still rest on wind-tunnel tests." and paras[1].endswith("fit for in practice.")
                      and [m.quote(c) for c in m.comments] == ["past fifteen years", "benchmarks that show", "Verification"]}
m = mk()
st, msg = DA.sync_one(m, [("main research directions of the past fifteen years", "main research directions of the past twenty years")])
R["D3_批注所在句被改批注仍在"] = {"status": st, "n_comments": len(m.comments), "c1_quote": m.quote(m.comments[0]), "others": [m.quote(c) for c in m.comments[1:]],
                          "pass": st == "已同步" and len(m.comments) == 3 and "past" in m.quote(m.comments[0]) and [m.quote(c) for c in m.comments[1:]] == ["benchmarks that show", "Verification"]}
m = mk(); orig_get = m.get; calls = {"n": 0}
def racing_get():
    calls["n"] += 1
    d, c = orig_get()
    if calls["n"] == 1:  # Liang Hu 在我们取文档之后、提交之前又打了字
        m.text = m.text.replace("Thrust 3. Verification", "Thrust 3. Verification and validation"); m.rev += 1
        for cc in m.comments: pass
    return d, c
m.get = racing_get
st, msg = DA.sync_one(m, [("how far each tool reproduces", "how far each computational tool reproduces")])
R["D4_修订号不符重做"] = {"status": st, "gets": calls["n"], "pi_text_kept": "Verification and validation" in m.text, "edit_done": "each computational tool" in m.text,
                     "pass": st == "已同步" and calls["n"] == 2 and "Verification and validation" in m.text and "each computational tool" in m.text}
# D5：句上有未处理的建议修订
m = mk(); d, _ = m.get()
d["body"]["content"][2]["paragraph"]["elements"][0]["textRun"]["suggestedInsertionIds"] = ["sug1"]
reqs, why = DA.plan_edit(d, [("how far each tool reproduces", "how far each computational tool reproduces")])
R["D5_有建议修订不改"] = {"reqs": reqs, "why": why, "pass": reqs is None and "建议修订" in why}
print(json.dumps(R, ensure_ascii=False, indent=1))
