#!/usr/bin/env python3
"""本地核对：写入修订/批注前后，非文字部件是否原样；全部接受/全部拒绝/逐条接受拒绝后的文字是否正确。输出 JSON。"""
import hashlib, json, re, sys, zipfile, difflib
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from ooxml_suggest import Doc, accept_reject, plain
from lxml import etree
b, a, sj = sys.argv[1:4]
S = json.load(open(sj))
zb, za = zipfile.ZipFile(b), zipfile.ZipFile(a)
nb, na = set(zb.namelist()), set(za.namelist())
textual = re.compile(r"word/(document|header\d*|footer\d*|comments)\.xml$|word/_rels/document\.xml\.rels$|\[Content_Types\]\.xml$")
same = {n: hashlib.sha1(zb.read(n)).hexdigest() == hashlib.sha1(za.read(n)).hexdigest() for n in nb if not textual.match(n)}
def counts(z):
    d = z.read("word/document.xml").decode()
    return {"图片 w:drawing": d.count("<w:drawing"), "表格 w:tbl": d.count("<w:tbl>"), "文本框 txbxContent": d.count("txbxContent>") // 2,
            "分节 sectPr": d.count("<w:sectPr"), "两栏 cols num=2": len(re.findall(r'w:num="2"', d)), "编号段 numPr": d.count("<w:numPr")}
def xmlok(z):
    for n in z.namelist():
        if n.endswith(".xml") or n.endswith(".rels"):
            etree.fromstring(z.read(n))
    return True
R = {"新增部件": sorted(na - nb), "缺失部件": sorted(nb - na), "非文字部件逐字节相同": all(same.values()), "非文字部件数": len(same),
     "媒体文件": [n for n in nb if n.startswith("word/media/")], "结构计数_前": counts(zb), "结构计数_后": counts(za), "XML 全部可解析": xmlok(za)}
d = za.read("word/document.xml").decode() + "".join(za.read(n).decode() for n in za.namelist() if re.match(r"word/header\d*\.xml", n))
ids = re.findall(r'<w:(?:ins|del) w:id="(\d+)"', d)
R["修订条数(ins+del)"] = len(ids); R["批注条数"] = za.read("word/comments.xml").decode().count("<w:comment ") if "word/comments.xml" in na else 0
tmp = "/tmp/l2625_chk.docx"
accept_reject(a, tmp, "accept"); acc = plain(tmp)
accept_reject(a, tmp, "reject"); rej = plain(tmp)
pb = plain(b)
R["全部拒绝＝原文"] = rej == pb
exp = list(pb)
for s in S:
    if s["kind"] == "edit":
        exp = [x.replace(s["old"], s["new"]) for x in exp]
R["全部接受＝按建议改后的文字"] = acc == exp
# 逐条：只接受第 1、3 条建议对应的修订，其余拒绝
first_ids = sorted(set(ids))
half = set(first_ids[: len(first_ids) // 2])
accept_reject(a, tmp, "accept", ids=half); accept_reject(tmp, tmp + "2.docx", "reject"); mix = plain(tmp + "2.docx")
R["逐条接受一半、拒绝其余后与原文/全改都不同(说明逐条生效)"] = mix != pb and mix != acc
R["文字差异_接受全部"] = [l for l in difflib.unified_diff(pb, acc, "写入前", "全部接受后", lineterm="", n=0) if not l.startswith("@@")]
print(json.dumps(R, ensure_ascii=False, indent=1))
