#!/usr/bin/env python3
"""L26.25 · 把修改建议写进原生 docx：w:ins/w:del 修订＋w:comment 批注（不碰图片、表格、版式等其他部件）。

用法：ooxml_suggest.py <in.docx> <out.docx> <suggestions.json>
suggestions.json：[{"kind":"edit","old":"…","new":"…","author":"Lead"},{"kind":"comment","anchor":"…","text":"…","author":"Lead"}]
另有 accept_reject(docx, mode, ids) 供核对：逐条接受/拒绝修订。

做法：在 document.xml / header*.xml / footer*.xml 的每个段落（含表格、文本框里的段落）里，把直接子 run 的文字拼起来找原句；
只把真正改了的词（按词 diff）包成 <w:del>＋<w:ins>，新文字沿用被替换处的字符格式；其余 run 原样不动。
"""
import copy, datetime, difflib, json, re, sys, zipfile
from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
q = lambda t: "{%s}%s" % (W, t)
CT_COMMENTS = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
REL_COMMENTS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"


def runs_of(p):
    """段落的直接子 run（不进文本框里的嵌套段落），及其文字。"""
    out = []
    for r in p.findall("w:r", NS):
        t = "".join((x.text or "") for x in r.findall("w:t", NS))
        if r.find("w:t", NS) is not None or t:
            out.append((r, t))
    return out


def split_run(r, k):
    """把 run 在第 k 个字符处切成两个，返回 (左, 右)。只处理只含一个 w:t 的 run（python-docx/Word 常见）。"""
    ts = r.findall("w:t", NS)
    if len(ts) != 1:
        raise ValueError("run 含多个文本节点，暂不切分")
    t = ts[0].text or ""
    if k <= 0 or k >= len(t):
        return (None, r) if k <= 0 else (r, None)
    r2 = copy.deepcopy(r)
    ts[0].text = t[:k]
    r2.find("w:t", NS).text = t[k:]
    for x in (ts[0], r2.find("w:t", NS)):
        x.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    r.addnext(r2)
    return r, r2


def isolate(p, a, b):
    """让段落文字 [a,b) 恰好由若干完整 run 覆盖，返回这些 run（按顺序）。"""
    pos = 0
    for r, t in runs_of(p):
        s, e = pos, pos + len(t)
        if s < a < e:
            split_run(r, a - s)
            return isolate(p, a, b)
        if s < b < e:
            split_run(r, b - s)
            return isolate(p, a, b)
        pos = e
    sel, pos = [], 0
    for r, t in runs_of(p):
        if pos >= a and pos + len(t) <= b and t:
            sel.append(r)
        pos += len(t)
    return sel


def run_at(p, a):
    """文字位置 a 处（或其前）的 run，用于插入点与格式继承。"""
    pos, last = 0, None
    for r, t in runs_of(p):
        if pos + len(t) >= a and t:
            return r, a - pos
        pos += len(t)
        last = r
    return last, None


class Doc:
    def __init__(self, path):
        z = zipfile.ZipFile(path)
        self.files = {n: z.read(n) for n in z.namelist()}
        self.order = z.namelist()
        self.parts = {n: etree.fromstring(self.files[n]) for n in self.files
                      if re.match(r"word/(document|header\d*|footer\d*)\.xml$", n)}
        self.rid = 9000
        self.cid = self._max_comment_id() + 1
        self.date = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.comments = etree.fromstring(self.files["word/comments.xml"]) if "word/comments.xml" in self.files else None

    def _max_comment_id(self):
        if "word/comments.xml" not in self.files:
            return -1
        ids = re.findall(rb'w:id="(\d+)"', self.files["word/comments.xml"])
        return max([int(i) for i in ids] or [-1])

    def paragraphs(self):
        for n, root in self.parts.items():
            for p in root.iter(q("p")):
                yield n, p

    def find(self, text):
        hits = []
        for n, p in self.paragraphs():
            full = "".join(t for _, t in runs_of(p))
            i = full.find(text)
            while i >= 0:
                hits.append((n, p, i))
                i = full.find(text, i + 1)
        return hits

    def _mk(self, tag, author):
        self.rid += 1
        return etree.Element(q(tag), {q("id"): str(self.rid), q("author"): author, q("date"): self.date})

    def edit(self, old, new, author="Lead"):
        hits = self.find(old)
        if len(hits) != 1:
            return False, f"原句命中 {len(hits)} 处（须唯一）"
        _, p, base = hits[0]
        tok = lambda s: [(m.group(), m.start()) for m in re.finditer(r"\s+|\w+|[^\w\s]", s)]
        A, B = tok(old), tok(new)
        sm = difflib.SequenceMatcher(None, [x for x, _ in A], [x for x, _ in B], autojunk=False)
        ops = [o for o in sm.get_opcodes() if o[0] != "equal"]
        n = 0
        for tag, i1, i2, j1, j2 in reversed(ops):  # 从后往前改，前面的位置不变
            a = base + (A[i1][1] if i1 < len(A) else len(old))
            b = base + (A[i2 - 1][1] + len(A[i2 - 1][0]) if i2 > i1 else (A[i1][1] if i1 < len(A) else len(old)))
            ins_text = "".join(x for x, _ in B[j1:j2])
            anchor_rpr = None
            if b > a:
                sel = isolate(p, a, b)
                if not sel:
                    return False, "定位到的文字跨了非文本元素，未改"
                anchor_rpr = sel[0].find("w:rPr", NS)
                d = self._mk("del", author)
                sel[0].addprevious(d)
                for r in sel:
                    for t in r.findall("w:t", NS):
                        t.tag = q("delText")
                    d.append(r)
                after = d
            else:
                r, k = run_at(p, a)
                if r is None:
                    return False, "找不到插入点"
                left, right = split_run(r, k) if k not in (None, 0) else (None, r)
                anchor_rpr = (left if left is not None else r).find("w:rPr", NS)
                after = left if left is not None else None
                if after is None:
                    after = etree.Element(q("bookmarkStart"))  # 临时占位
                    r.addprevious(after)
            if ins_text:
                ins = self._mk("ins", author)
                nr = etree.SubElement(ins, q("r"))
                if anchor_rpr is not None:
                    nr.append(copy.deepcopy(anchor_rpr))
                t = etree.SubElement(nr, q("t"))
                t.text = ins_text
                t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                after.addnext(ins)
            if after.tag == q("bookmarkStart") and not after.attrib:
                after.getparent().remove(after)
            n += 1
        return True, f"写入 {n} 处修订"

    def comment(self, anchor, text, author="Lead"):
        hits = self.find(anchor)
        if len(hits) != 1:
            return False, f"锚定原文命中 {len(hits)} 处（须唯一）"
        part, p, a = hits[0]
        if part != "word/document.xml":
            return False, "批注只放正文"
        sel = isolate(p, a, a + len(anchor))
        cid = str(self.cid)
        self.cid += 1
        sel[0].addprevious(etree.Element(q("commentRangeStart"), {q("id"): cid}))
        end = etree.Element(q("commentRangeEnd"), {q("id"): cid})
        sel[-1].addnext(end)
        ref = etree.Element(q("r"))
        rpr = etree.SubElement(ref, q("rPr"))
        etree.SubElement(rpr, q("rStyle"), {q("val"): "CommentReference"})
        etree.SubElement(ref, q("commentReference"), {q("id"): cid})
        end.addnext(ref)
        if self.comments is None:
            self.comments = etree.Element(q("comments"), nsmap={"w": W})
        c = etree.SubElement(self.comments, q("comment"), {q("id"): cid, q("author"): author, q("date"): self.date, q("initials"): author[:2]})
        cp = etree.SubElement(c, q("p"))
        cr = etree.SubElement(cp, q("r"))
        etree.SubElement(cr, q("t")).text = text
        return True, f"批注 {cid}"

    def save(self, path):
        files = dict(self.files)
        for n, root in self.parts.items():
            files[n] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        order = list(self.order)
        if self.comments is not None:
            files["word/comments.xml"] = etree.tostring(self.comments, xml_declaration=True, encoding="UTF-8", standalone=True)
            if "word/comments.xml" not in order:
                order.append("word/comments.xml")
                ct = files["[Content_Types].xml"].decode()
                if "/word/comments.xml" not in ct:
                    ct = ct.replace("</Types>", f'<Override PartName="/word/comments.xml" ContentType="{CT_COMMENTS}"/></Types>')
                files["[Content_Types].xml"] = ct.encode()
                rels = files["word/_rels/document.xml.rels"].decode()
                if REL_COMMENTS not in rels:
                    rels = rels.replace("</Relationships>", f'<Relationship Id="rIdL2625c" Type="{REL_COMMENTS}" Target="comments.xml"/></Relationships>')
                files["word/_rels/document.xml.rels"] = rels.encode()
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for n in order:
                z.writestr(n, files[n])


def accept_reject(path, out, mode, ids=None):
    """逐条接受（mode=accept）或拒绝（reject）修订；ids=None 表示全部。"""
    d = Doc(path)
    for root in d.parts.values():
        for el in list(root.iter(q("ins"), q("del"))):
            if ids is not None and el.get(q("id")) not in ids:
                continue
            keep = (el.tag == q("ins")) == (mode == "accept")
            par = el.getparent()
            if keep:
                for r in el:
                    for t in r.findall("w:delText", NS):
                        t.tag = q("t")
                    el.addprevious(r)
            par.remove(el)
    d.save(out)


def plain(path):
    d = Doc(path)
    out = []
    for n, p in d.paragraphs():
        out.append("".join(t for _, t in runs_of(p)))
    return out


if __name__ == "__main__":
    src, dst, sj = sys.argv[1:4]
    d = Doc(src)
    log = []
    for s in json.load(open(sj, encoding="utf-8")):
        ok, msg = d.edit(s["old"], s["new"], s.get("author", "Lead")) if s["kind"] == "edit" else d.comment(s["anchor"], s["text"], s.get("author", "Lead"))
        log.append({"suggestion": s, "ok": ok, "msg": msg})
    d.save(dst)
    print(json.dumps(log, ensure_ascii=False, indent=1))
