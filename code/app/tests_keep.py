#!/usr/bin/env python3
"""L26.25：接受一条不丢其他（RS/LaTeX 版，测试副本＋模拟 Google 文档）。输出 JSON：每步条目数。"""
import hashlib, json, os, sys, time, urllib.request, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests_gdoc.py")).read().split("R = {}")[0])  # 复用 post/state/direct 等
FAKE = f"{WB}/fake_chat.jsonl"


def lead(edits):
    with open(FAKE, "a") as f:
        f.write(json.dumps({"id": "a-" + uuid.uuid4().hex[:8], "role": "assistant", "ts": time.time(),
                            "content": "建议：" + "".join("\n```wb-edit\n" + json.dumps(e) + "\n```\n" for e in edits)}) + "\n")


def snap():
    s = state(); E = [e for e in s["edits"] if e.get("status") != "重复"]
    chat = [e for e in E if not e.get("source")]; g = [e for e in E if e.get("source") == "gdoc" and e.get("live")]
    DONE = ("已接受", "已拒绝", "已忽略", "已处理", "已撤销", "已交 Lead", "已在稿中")
    return {"对话_待批": sum(e["status"] == "待批" for e in chat), "对话_需重新确认": sum(e["status"] == "需重新确认" for e in chat),
            "对话_已接受": sum(e["status"] == "已接受" for e in chat), "Google文档_未处理": sum(e["status"] not in DONE for e in g),
            "未处理合计": sum(e["status"] not in DONE for e in chat + g), "gdoc_pending": pending(), "gdoc_pending_file": pending_file()}


R = {}
post("/api/gdoc_refresh")
direct("The coupled wake oscillator captures", "The coupled wake-oscillator model captures")  # Liang Hu 在 Google 文档里改了一处（未处理）
post("/api/gdoc_refresh")
sha0 = hashlib.sha1(open(DOCX, "rb").read()).hexdigest()
E = [{"file": "main.tex", "old": "This test paper are used", "new": "This test paper is used", "why": "A 主谓一致"},
     {"file": "main.tex", "old": "test paper are used to evaluate", "new": "test paper is used to assess", "why": "B 与 A 原句重叠"},
     {"file": "main.tex", "old": "We considers a wake oscillator", "new": "We consider a wake oscillator", "why": "C"},
     {"file": "main.tex", "old": "coupled to a elastically mounted", "new": "coupled to an elastically mounted", "why": "D"},
     {"file": "main.tex", "old": "the coupling term and it's effect", "new": "the coupling term and its effect", "why": "E"}]
lead(E)
ids = {e["why"][0]: e["id"] for e in state()["edits"] if not e.get("source") and e.get("status") == "待批"}
before = snap()
ra = post("/api/accept", {"id": ids["A"]})
after1 = snap()
b_item = next(e for e in state()["edits"] if e["id"] == ids["B"])
R["K1_接受一条其余仍在"] = {"before": before, "after": after1, "accept_msg": ra["msg"],
                       "pass": ra["ok"] and after1["对话_待批"] == 3 and after1["对话_需重新确认"] == 1 and after1["未处理合计"] == before["未处理合计"] - 1}
R["K2_重叠条目标需重新确认"] = {"B_status": b_item["status"], "B_note": b_item.get("note"), "pass": b_item["status"] == "需重新确认"}
R["K3_Google文档未处理不被覆盖"] = {"gdoc_pending_before_after": [before["gdoc_pending"], after1["gdoc_pending"]],
                              "google_doc_file_unchanged": hashlib.sha1(open(DOCX, "rb").read()).hexdigest() == sha0,
                              "pass": before["gdoc_pending"] == after1["gdoc_pending"] == 1 and hashlib.sha1(open(DOCX, "rb").read()).hexdigest() == sha0}
# K4 筛选：只看对话 → 全部接受（当前筛选的可写回条目＝C/D/E）；B（需重新确认）与 Google 文档那条不动
sel = [ids["C"], ids["D"], ids["E"]]
rm = post("/api/accept_many", {"ids": sel})
after2 = snap()
g_items = [e for e in state()["edits"] if e.get("source") == "gdoc" and e.get("live")]
R["K4_全部接受只作用于筛选"] = {"filtered_ids": len(sel), "msg": rm["msg"], "after": after2,
                           "gdoc_item_status": [e["status"] for e in g_items],
                           "pass": all(x["ok"] for x in rm["results"]) and after2["对话_待批"] == 0 and after2["对话_需重新确认"] == 1 and after2["Google文档_未处理"] == 1}
print(json.dumps(R, ensure_ascii=False, indent=1))
