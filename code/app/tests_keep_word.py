#!/usr/bin/env python3
"""L26.25：接受一条不丢其他（Word 版，模拟 OneDrive＋合成图文稿）。输出 JSON：每步条目数。"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests_word.py")).read().split("R = {}")[0])
DONE = ("已接受", "已拒绝", "已忽略", "已处理", "已撤销", "已交 Lead", "已在稿中")


def snap():
    E = [e for e in get("/api/state")["edits"] if e.get("status") != "重复"]
    chat = [e for e in E if not e.get("source")]; cm = [e for e in E if e.get("source") == "word"]
    return {"对话_待批": sum(e["status"] == "待批" for e in chat), "对话_需重新确认": sum(e["status"] == "需重新确认" for e in chat),
            "对话_已接受": sum(e["status"] == "已接受" for e in chat), "Word批注_未处理": sum(e["status"] not in DONE for e in cm),
            "未处理合计": sum(e["status"] not in DONE for e in chat + cm)}


R = {}
orig = open(ORIG, "rb").read()
post("/api/w_setdoc", {"link": "https://onedrive.live.com/edit.aspx?resid=TESTITEM%21101"})
d = Doc(ORIG); d.comment("Release open source code for practitioners.", "能否写明仓库地址？", author="Liang Hu")  # Liang Hu 在 Word 里的未处理批注
d.save("/tmp/l2625_kc.docx"); post("/test/pi_edit", raw=open("/tmp/l2625_kc.docx", "rb").read(), base=M); post("/api/refresh")
base_bytes = cur_bytes()
E = [{"file": "word", "old": "This proposal describe a new method", "new": "This proposal describes a new method", "why": "A"},
     {"file": "word", "old": "proposal describe a new method for", "new": "proposal outlines a new method for", "why": "B 与 A 重叠"},
     {"file": "word", "old": "3.8 (estimated)", "new": "3.8 (est.)", "why": "C"},
     {"file": "word", "old": "Validate the model againts field", "new": "Validate the model against field", "why": "D"},
     {"file": "word", "old": "Table 1 summarise the", "new": "Table 1 summarises the", "why": "E"}]
lead_says(E)
ids = {e["why"][0]: e["id"] for e in get("/api/state")["edits"] if not e.get("source") and e.get("status") == "待批"}
before = snap(); v0 = nvers()
ra = post("/api/accept", {"id": ids["A"]}); after1 = snap()
b = next(e for e in get("/api/state")["edits"] if e["id"] == ids["B"])
R["KW1_接受一条其余仍在"] = {"before": before, "after": after1, "msg": ra["msg"][:80], "new_versions": nvers() - v0,
                        "pass": ra["ok"] and after1["对话_待批"] == 3 and after1["对话_需重新确认"] == 1 and after1["未处理合计"] == before["未处理合计"] - 1}
R["KW2_重叠条目标需重新确认"] = {"B_status": b["status"], "pass": b["status"] == "需重新确认"}
cur = cur_bytes()
R["KW3_写回只加修订不动其他"] = {"Liang Hu批注还在": "能否写明仓库地址" in zipfile.ZipFile(io.BytesIO(cur)).read("word/comments.xml").decode(),
                           "非文字部件不变": nontext_same(base_bytes, cur), "Word批注_未处理_前后": [before["Word批注_未处理"], after1["Word批注_未处理"]]}
R["KW3_写回只加修订不动其他"]["pass"] = R["KW3_写回只加修订不动其他"]["Liang Hu批注还在"] and R["KW3_写回只加修订不动其他"]["非文字部件不变"] and after1["Word批注_未处理"] == 1
rm = post("/api/accept_many", {"ids": [ids["C"], ids["D"], ids["E"]]}); after2 = snap()
R["KW4_全部接受只作用于筛选"] = {"msg": rm["msg"], "after": after2, "new_versions_total": nvers() - v0,
                            "pass": all(x["ok"] for x in rm["results"]) and after2["对话_待批"] == 0 and after2["对话_需重新确认"] == 1 and after2["Word批注_未处理"] == 1}
# 全部拒绝＝原稿（含 Liang Hu 的批注那一版）
open("/tmp/l2625_kf.docx", "wb").write(cur_bytes()); accept_reject("/tmp/l2625_kf.docx", "/tmp/l2625_kr.docx", "reject")
R["KW5_全部拒绝等于写回前"] = {"pass": plain_of(open("/tmp/l2625_kr.docx", "rb").read()) == plain_of(base_bytes) and nontext_same(base_bytes, open("/tmp/l2625_kr.docx", "rb").read())}
print(json.dumps(R, ensure_ascii=False, indent=1))
