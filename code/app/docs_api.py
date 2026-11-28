#!/usr/bin/env python3
"""L26.25 原生 Google 文档定点写回（11-16）：用 Docs API documents.batchUpdate 只改一处，保留批注与建议。

令牌不在本程序里：读文档、提交修改都经平台的 `rc-gdoc docs-get / docs-batch`（令牌只在 rc-gdoc 进程内）。
本文件只做两件事：
  1) plan_edit(doc_json, old, new_parts) —— 在文档里唯一定位原句，按词比对生成最小的 deleteContentRange / insertText 请求；
     新增段用「\n」插入（Docs 里插入换行即分出新段，新段沿用所在段样式）。
  2) Client —— 调 rc-gdoc；MockClient —— 测试用的内存文档（含批注锚点随编辑平移），验证请求本身改对了、没碰别处。
"""
import copy, difflib, json, os, re, subprocess, tempfile

TOK = re.compile(r"\s+|\w+|[^\w\s]")


def _walk(content, out):
    for el in content or []:
        if "paragraph" in el:
            for pe in el["paragraph"].get("elements", []):
                tr = pe.get("textRun")
                if tr is None:
                    out.append(("obj", pe.get("startIndex"), pe.get("endIndex"), "", False))
                    continue
                sug = bool(tr.get("suggestedInsertionIds") or tr.get("suggestedDeletionIds"))
                out.append(("text", pe["startIndex"], pe["endIndex"], tr.get("content", ""), sug))
        elif "table" in el:
            for row in el["table"].get("tableRows", []):
                for cell in row.get("tableCells", []):
                    _walk(cell.get("content"), out)


def text_map(doc):
    """返回 (全文, 每个字符的文档下标, 每个字符是否属于未处理建议)。非文本元素处断开（用 \x00 占位，不会被匹配到）。"""
    segs = []
    _walk(doc.get("body", {}).get("content"), segs)
    T, IX, SG = [], [], []
    for kind, a, b, t, sug in segs:
        if kind != "text":
            T.append("\x00"); IX.append(a); SG.append(True)
            continue
        for k, ch in enumerate(t):
            T.append(ch); IX.append(a + k); SG.append(sug)
    return "".join(T), IX, SG


def has_suggestions(doc):
    return bool(re.search(r'"suggested(Insertion|Deletion)Ids"', json.dumps(doc)))


def sync_one(client, old_variants, tries=3):
    """取文档 → 定点改 → 带修订号提交；修订号不符就在最新版本上重做。返回 (状态, 说明)。"""
    for _ in range(tries):
        doc, _c = client.get()
        reqs, why = plan_edit(doc, old_variants, None)
        if reqs is None:
            return "需重新确认", why
        if not reqs:
            return "已同步", why
        ok, msg = client.batch(reqs, doc.get("revisionId"))
        if ok:
            return "已同步", why + "（定点写回，批注与建议保留）"
        if "修订号" not in msg:
            return "失败", "定点写回失败：" + msg
    return "失败", "文档一直在变（你可能正在连续输入），稍后自动重试"


def plan_edit(doc, old_variants, _unused=None):
    """old_variants: [(old, new_joined_by_\\n)]（不同撇号/空格写法）。返回 (requests, 说明) 或 (None, 不能改的原因)。"""
    T, IX, SG = text_map(doc)
    why = "文档里找不到这句原文（可能你已在文档里改过）"
    for old, new in old_variants:
        n = T.count(old)
        if n == 0:
            if all(T.count(x) == 1 for x in new.split("\n") if x.strip()):
                return [], "文档里已经是新写法"
            continue
        if n > 1:
            why = "文档里这句出现不止一处"
            continue
        base = T.index(old)
        if any(SG[base:base + len(old)]):
            return None, "这句上有未处理的建议修订或非文本元素，未改（交 Lead）"
        if IX[base + len(old) - 1] - IX[base] != len(old) - 1:
            return None, "这句跨了非文本元素，未改（交 Lead）"
        A = [(m.group(), m.start()) for m in TOK.finditer(old)]
        B = [(m.group(), m.start()) for m in TOK.finditer(new)]
        ops = [o for o in difflib.SequenceMatcher(None, [x for x, _ in A], [x for x, _ in B], autojunk=False).get_opcodes() if o[0] != "equal"]
        reqs = []
        for tag, i1, i2, j1, j2 in reversed(ops):  # 从后往前改，前面的下标不受影响
            a = A[i1][1] if i1 < len(A) else len(old)
            b = (A[i2 - 1][1] + len(A[i2 - 1][0])) if i2 > i1 else a
            ins = "".join(x for x, _ in B[j1:j2])
            at = IX[base] + a
            if b > a:
                reqs.append({"deleteContentRange": {"range": {"startIndex": at, "endIndex": IX[base] + b}}})
            if ins:
                reqs.append({"insertText": {"location": {"index": at}, "text": ins}})
        return reqs, f"改了 {len(ops)} 处" + (f"；新增 {new.count(chr(10))} 段" if "\n" in new else "")
    return None, why


class Client:
    """经 rc-gdoc 调 Docs API；令牌只在 rc-gdoc 里。"""

    def __init__(self, rel, rcgdoc=os.path.expanduser("~/bin/rc-gdoc")):
        self.rel, self.cmd = rel, rcgdoc

    def get(self):
        d = tempfile.mkdtemp(prefix="l2625_docs_")
        out = os.path.join(d, "doc.json")
        r = subprocess.run([self.cmd, "docs-get", self.rel, out], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise RuntimeError("docs-get 失败：" + (r.stderr or r.stdout)[-200:])
        doc = json.load(open(out))
        cpath = out[:-5] + ".comments.json"
        comments = json.load(open(cpath)) if os.path.exists(cpath) else None
        return doc, comments

    def batch(self, requests, revision):
        d = tempfile.mkdtemp(prefix="l2625_docs_")
        p = os.path.join(d, "req.json")
        json.dump({"requests": requests, "writeControl": {"requiredRevisionId": revision}}, open(p, "w"))
        r = subprocess.run([self.cmd, "docs-batch", self.rel, p], capture_output=True, text=True, timeout=120)
        if r.returncode == 3:
            return False, "文档刚被改过（修订号不符），稍后在最新版本上重做"
        return r.returncode == 0, (r.stdout or r.stderr)[-200:]


class MockClient:
    """测试用：内存里的 Docs 文档（只含正文段落）＋按下标锚定的批注，执行 insertText/deleteContentRange 时批注锚点随之平移。"""

    def __init__(self, paragraphs, comments):
        self.text = "".join(p + "\n" for p in paragraphs)  # Docs 正文从下标 1 开始
        self.comments = [dict(c) for c in comments]       # {id, start, end, quote}
        self.rev = 1

    def doc(self):
        content, i = [], 1
        for p in self.text.split("\n")[:-1]:
            content.append({"paragraph": {"elements": [{"startIndex": i, "endIndex": i + len(p) + 1, "textRun": {"content": p + "\n"}}]}})
            i += len(p) + 1
        return {"revisionId": str(self.rev), "body": {"content": content}}

    def get(self):
        return self.doc(), [dict(c) for c in self.comments]

    def batch(self, requests, revision):
        if revision != str(self.rev):
            return False, "文档刚被改过（修订号不符）"
        for rq in requests:
            if "deleteContentRange" in rq:
                a, b = rq["deleteContentRange"]["range"]["startIndex"], rq["deleteContentRange"]["range"]["endIndex"]
                self.text = self.text[:a - 1] + self.text[b - 1:]
                for c in self.comments:
                    for k in ("start", "end"):
                        c[k] = c[k] if c[k] <= a else (a if c[k] < b else c[k] - (b - a))
            elif "insertText" in rq:
                at, t = rq["insertText"]["location"]["index"], rq["insertText"]["text"]
                self.text = self.text[:at - 1] + t + self.text[at - 1:]
                for c in self.comments:
                    c["start"] += len(t) if c["start"] >= at else 0
                    c["end"] += len(t) if c["end"] > at else 0
            else:
                return False, "不支持的请求"
        self.rev += 1
        return True, "ok"

    def quote(self, c):
        return self.text[c["start"] - 1:c["end"] - 1]
