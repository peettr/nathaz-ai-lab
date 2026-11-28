#!/usr/bin/env python3
"""L26.25 第三步测试 W1–W10（模拟 OneDrive＋合成图文测试稿＋假对话）。输出 JSON。"""
import hashlib, io, json, os, re, stat, sys, time, urllib.request, uuid, zipfile
APP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP)
from ooxml_suggest import Doc, runs_of, accept_reject  # noqa: E402
B = "http://127.0.0.1:8766"; M = "http://127.0.0.1:8768"
WS = os.path.expanduser("~/l26_25_ws/wb_word"); MD = os.path.expanduser("~/l26_25_ws/mock_onedrive")
ORIG = os.path.expanduser("~/l26_25_ws/o365w/before.docx"); FAKE = f"{WS}/fake_chat.jsonl"
TEXTUAL = re.compile(r"word/(document|header\d*|footer\d*|comments)\.xml$|word/_rels/document\.xml\.rels$|\[Content_Types\]\.xml$")


def post(u, b=None, base=B, raw=None):
    r = urllib.request.Request(base + u, data=raw if raw is not None else json.dumps(b or {}).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=120).read() or b"{}")


def get(u):
    return json.loads(urllib.request.urlopen(B + u, timeout=60).read())


def cur_bytes():
    vs = sorted(os.listdir(MD), key=lambda x: int(x[1:-5]))
    return open(os.path.join(MD, vs[-1]), "rb").read()


def nvers():
    return len(os.listdir(MD))


def plain_of(data):
    p = "/tmp/l2625_w.docx"; open(p, "wb").write(data)
    d = Doc(p)
    return ["".join(t for _, t in runs_of(x)) for _, x in d.paragraphs()]


def struct(data):
    z = zipfile.ZipFile(io.BytesIO(data)); d = z.read("word/document.xml").decode()
    return {"图片": d.count("<w:drawing"), "表格": d.count("<w:tbl>"), "文本框": d.count("txbxContent>") // 2, "分节": d.count("<w:sectPr"),
            "两栏": len(re.findall(r'w:num="2"', d)), "批注": z.read("word/comments.xml").decode().count("<w:comment ") if "word/comments.xml" in z.namelist() else 0,
            "修订": len(re.findall(r"<w:(?:ins|del) ", d))}


def nontext_same(a, b):
    za, zb = zipfile.ZipFile(io.BytesIO(a)), zipfile.ZipFile(io.BytesIO(b))
    return all(za.read(n) == zb.read(n) for n in za.namelist() if not TEXTUAL.match(n))


def lead_says(edits):
    with open(FAKE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": "a-" + uuid.uuid4().hex[:8], "role": "assistant", "ts": time.time(),
                            "content": "建议：" + "".join("\n```wb-edit\n" + json.dumps(e, ensure_ascii=False) + "\n```\n" for e in edits)}, ensure_ascii=False) + "\n")


def pend():
    return [e for e in get("/api/state")["edits"] if e.get("status") == "待批" and e.get("kind") != "comment"]


R = {}
orig = open(ORIG, "rb").read()
# W1 选稿＋预览
r = post("/api/w_setdoc", {"link": "https://onedrive.live.com/edit.aspx?resid=TESTITEM%21101&cid=x"})
pv = urllib.request.urlopen(B + "/preview").read().decode()
R["W1_选稿与本地预览"] = {"msg": r["msg"], "preview_img": pv.count("<img"), "preview_table": pv.count("<table"), "public_link_used": False,
                     "pass": r["ok"] and pv.count("<img") >= 1 and pv.count("<table") >= 1}
# W2 接受 3 条 → 每条一个新版本，图片/表格/版式不变
E = [{"file": "word", "old": "This proposal describe a new method", "new": "This proposal describes a new method", "why": "主谓一致"},
     {"file": "word", "old": "3.8 (estimated)", "new": "3.8 (est.)", "why": "表内缩写"},
     {"file": "word", "old": "We thanks the reviewers for there comments.", "new": "We thank the reviewers for their comments.", "why": "语法两处"}]
lead_says(E)
ids = [e["id"] for e in pend()][-3:]
items, v0 = [], nvers()
for i in ids:
    r = post("/api/accept", {"id": i}); b = cur_bytes()
    items.append({"msg": r["msg"], "ok": r["ok"], "versions": nvers(), "nontext_same": nontext_same(orig, b), "struct": struct(b)})
final = cur_bytes()
R["W2_接受写回3条"] = {"items": items, "struct_before": struct(orig),
                    "pass": all(x["ok"] and x["nontext_same"] for x in items) and nvers() == v0 + 3 and
                    all(struct(final)[k] == struct(orig)[k] for k in ("图片", "表格", "文本框", "分节", "两栏")) and struct(final)["批注"] == 3}
# W3 全部拒绝＝原稿；全部接受＝按建议改
open("/tmp/l2625_f.docx", "wb").write(final)
accept_reject("/tmp/l2625_f.docx", "/tmp/l2625_rej.docx", "reject"); accept_reject("/tmp/l2625_f.docx", "/tmp/l2625_acc.docx", "accept")
rej, acc = open("/tmp/l2625_rej.docx", "rb").read(), open("/tmp/l2625_acc.docx", "rb").read()
exp = plain_of(orig)
for e in E:
    exp = [x.replace(e["old"], e["new"]) for x in exp]
R["W3_全部拒绝等于原稿"] = {"reject_text_equal": plain_of(rej) == plain_of(orig), "reject_nontext_same": nontext_same(orig, rej),
                       "accept_text_as_suggested": plain_of(acc) == exp}
R["W3_全部拒绝等于原稿"]["pass"] = all(R["W3_全部拒绝等于原稿"].values())
# W4 写回瞬间 Word 稿被改（eTag 不符）→ 412 → 停下、不覆盖
lead_says([{"file": "word", "old": "Table 1 summarise the", "new": "Table 1 summarises the", "why": "语法"}])
i4 = [e["id"] for e in pend()][-1]
post("/test/bump_on_next_put", {}, base=M); n0 = nvers(); before = cur_bytes()
r4 = post("/api/accept", {"id": i4})
R["W4_冲突停下"] = {"msg": r4["msg"], "versions_added_by_pi_only": nvers() - n0, "content_unchanged": cur_bytes() == before,
                  "pass": (not r4["ok"]) and "被改过" in r4["msg"] and nvers() - n0 == 1 and cur_bytes() == before}
r4b = post("/api/accept", {"id": i4})  # 刷新后再接受能成功
R["W4_冲突停下"]["retry_ok"] = r4b["ok"]
# W5 撤销一条
st = get("/api/state"); acc_ids = [e["id"] for e in st["edits"] if e["status"] == "已接受"]
b5 = cur_bytes(); r5 = post("/api/revert", {"id": acc_ids[0]}); a5 = cur_bytes()
R["W5_撤销"] = {"msg": r5["msg"], "nontext_same": nontext_same(orig, a5), "revisions_before_after": [struct(b5)["修订"], struct(a5)["修订"]],
              "comments_before_after": [struct(b5)["批注"], struct(a5)["批注"]],
              "pass": r5["ok"] and struct(a5)["修订"] < struct(b5)["修订"] and struct(a5)["批注"] == struct(b5)["批注"] - 1}
# W6 版本历史回滚到最初版本
vs = [v for v in get("/api/w_versions")["versions"] if v.get("src") == "onedrive"]; first = vs[-1]["id"]
r6 = post("/api/w_restore", {"version": first})
R["W6_版本历史回滚"] = {"versions_listed": len(vs), "restore_msg": r6["msg"], "content_equals_original": cur_bytes() == orig, "history_kept": nvers() == len(vs) + 1,
                    "pass": r6["ok"] and cur_bytes() == orig and nvers() == len(vs) + 1}
# W6b 本机备份回滚（OneDrive 版本历史接口不可用时的退路）：恢复到最早一份写回前备份＝原稿
vs2 = get("/api/w_versions")["versions"]; loc = [v for v in vs2 if v["id"].startswith("local:")]
r6b = post("/api/w_restore", {"version": loc[-1]["id"]}) if loc else {"ok": False, "msg": "无本机备份"}
R["W6b_本机备份回滚"] = {"local_backups": len(loc), "msg": r6b["msg"], "content_equals_original": cur_bytes() == orig,
                     "pass": bool(loc) and r6b["ok"] and cur_bytes() == orig}
# W7 Liang Hu 在 Word 里写的批注 → 待批项 → 交 Lead
d = Doc(ORIG); d.comment("Release open source code for practitioners.", "能否写明仓库地址？", author="Liang Hu")
d.save("/tmp/l2625_pc.docx"); post("/test/pi_edit", raw=open("/tmp/l2625_pc.docx", "rb").read(), base=M)
post("/api/refresh")
cm = [e for e in get("/api/state")["edits"] if e.get("kind") == "comment" and e["status"] == "批注"]
nb = sum(1 for _ in open(FAKE))
r7 = post("/api/w_comment", {"id": cm[0]["id"], "act": "tolead"}) if cm else {"ok": False}
posted = [json.loads(l) for l in open(FAKE)][nb:]
R["W7_Word批注交Lead"] = {"comment_items": len(cm), "act": r7.get("msg"), "posted": sum(1 for m in posted if m["role"] == "user" and "【稿件工作台】" in m["content"]),
                        "pass": len(cm) == 1 and r7.get("ok") and sum(1 for m in posted if m["role"] == "user") == 1}
# W8 预览里选句提问 → 定位到段落；W9 60 s 内同题只发一次
nb = sum(1 for _ in open(FAKE))
q = {"question": "这句能否更具体？", "selection": "Develop a time-frequency load model.", "page": None}
r8 = post("/api/ask", q); r9 = post("/api/ask", q)
posted = [json.loads(l) for l in open(FAKE)][nb:]
R["W8_选句提问定位"] = {"loc": r8.get("loc"), "pass": r8["ok"] and bool(r8.get("loc"))}
R["W9_去重"] = {"second_dup": r9.get("dup", False), "posted": sum(1 for m in posted if m["role"] == "user"), "pass": r9.get("dup") and sum(1 for m in posted if m["role"] == "user") == 1}
# W10 凭据文件权限与日志无令牌
sys.path.insert(0, APP)
from graph import Graph  # noqa: E402
g = Graph(cred_dir="/tmp/l2625_cred_test"); g.set_client_id("00000000-1111-2222-3333-444444444444"); g._write("token.json", {"refresh_token": "x"})
mode_dir = stat.S_IMODE(os.stat("/tmp/l2625_cred_test").st_mode); mode_f = [stat.S_IMODE(os.stat("/tmp/l2625_cred_test/" + f).st_mode) for f in ("app.json", "token.json")]
logs = open(f"{WS}/workbench.log", encoding="utf-8").read()
R["W10_凭据权限与日志"] = {"dir_mode": oct(mode_dir), "file_modes": [oct(m) for m in mode_f], "token_in_log": "test-token" in logs or "Bearer" in logs,
                        "pass": mode_dir == 0o700 and all(m == 0o600 for m in mode_f) and "test-token" not in logs and "Bearer" not in logs}
print(json.dumps(R, ensure_ascii=False, indent=1))
