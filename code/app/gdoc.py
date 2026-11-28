"""L26.25 工作台 · Google 文档（Drive 里的 docx 批注版）改动识别。只读 Google 文档，不往 Drive 写。

思路：docx 是从 LaTeX 生成的，正文逐段能和 LaTeX 词序对齐（实测 RS 51 段里 50 段完全对齐，只有标题行不同）。
- 段落对不上 LaTeX → 有人改过。和「基线」（上次完全对齐时的 docx 快照）比：
    基线段＝现段            → Overleaf 后来改的（Google 文档落后），不算待批
    基线段≠现段、基线对得上 LaTeX → Google 文档里改的 → 生成待批修改
    基线段≠现段、基线也对不上   → 两边都改了 → 冲突，列给 Liang Hu 选
- 建议修订（w:ins/w:del）：改前文字＝去掉插入、保留删除；改后＝现文字。
- 批注（comments.xml）：列出锚定原文和批注内容。
"""
import difflib, hashlib, re, zipfile
from xml.sax.saxutils import unescape

WORD = re.compile(r"[A-Za-z0-9]+")
TOK = re.compile(r"\w+|[^\w\s]")


def _x(s):
    return unescape(s, {"&quot;": '"', "&apos;": "'"})


def _texts(xml, tag="w:t"):
    return "".join(_x(t) for t in re.findall(rf"<{tag}(?:\s[^>]*)?>([^<]*)</{tag}>", xml))


def parse_docx(path):
    z = zipfile.ZipFile(path)
    d = z.read("word/document.xml").decode("utf-8")
    paras = []
    for p in re.findall(r"<w:p[ >].*?</w:p>", d, re.S):
        cur = _texts(p)  # w:t 含插入、不含删除（删除在 w:delText）
        tracked = "<w:ins " in p or "<w:del " in p
        old = cur
        if tracked:
            q = re.sub(r"<w:ins [^>]*>.*?</w:ins>", "", p, flags=re.S)
            q = re.sub(r"<w:delText([^>]*)>", r"<w:t\1>", q).replace("</w:delText>", "</w:t>")
            old = _texts(q)
        if cur.strip() or old.strip():
            paras.append({"cur": cur, "old": old, "tracked": tracked})
    comments = []
    if "word/comments.xml" in z.namelist():
        c = z.read("word/comments.xml").decode("utf-8")
        for m in re.finditer(r'<w:comment [^>]*w:id="(\d+)"([^>]*)>(.*?)</w:comment>', c, re.S):
            cid, attrs, body = m.groups()
            au = re.search(r'w:author="([^"]*)"', m.group(0))
            a = re.search(rf'<w:commentRangeStart [^>]*w:id="{cid}"[^>]*/>(.*?)<w:commentRangeEnd [^>]*w:id="{cid}"[^>]*/>', d, re.S)
            comments.append({"cid": cid, "author": _x(au.group(1)) if au else "", "text": _texts(body),
                             "anchor": _texts(a.group(1)) if a else ""})
    return paras, comments


# ---------- 与 LaTeX 对齐 ----------
def tex_seq(src):
    s = re.sub(r"(?<!\\)%[^\n]*", lambda m: " " * len(m.group()), src)
    s = re.sub(r"\\[a-zA-Z]+\*?", lambda m: " " * len(m.group()), s)
    seq = [m.group().lower() for m in WORD.finditer(s)]
    idx = {}
    for k, w in enumerate(seq):
        idx.setdefault(w, []).append(k)
    return seq, idx


def coverage(text, seq, idx):
    pw = [w.lower() for w in WORD.findall(text) if not w.isdigit()]  # 纯数字多来自 \\ref 编号，不参与对齐
    if len(pw) < 3:
        return 1.0
    rare = min(range(len(pw)), key=lambda q: len(idx.get(pw[q], [])) or 1e9)
    best = 0.0
    for x in idx.get(pw[rare], [])[:200]:
        a, h = max(0, x - rare - 3), 0
        for w in pw:
            f = next((y for y in range(a, min(a + 6, len(seq))) if seq[y] == w), None)
            if f is not None:
                h, a = h + 1, f + 1
        best = max(best, h / len(pw))
    return best


def aligned(text, seq, idx):
    """严格对齐：段内每个词都按顺序出现在 LaTeX 里（只允许 LaTeX 多出少量词，如命令参数）。"""
    return coverage(text, seq, idx) >= 0.999


# ---------- 纯文字改动 → LaTeX 修改 ----------
MAPS = [{}, {"“": "``", "”": "''", "‘": "`", "’": "'"}, {"“": "``", "”": "''", "‘": "`", "’": "'", "\u00a0": "~", "—": "---", "–": "--"}]


def _conv(s, mp):
    for a, b in mp.items():
        s = s.replace(a, b)
    return s


def segments(old, new, ctx=3, gap=6):
    """按词/标点对比，把改动分组，每组左右各带 ctx 个词作定位上下文。返回 [(old_seg, new_seg)]。"""
    ot = [(m.group(), m.start(), m.end()) for m in TOK.finditer(old)]
    nt = [(m.group(), m.start(), m.end()) for m in TOK.finditer(new)]
    sm = difflib.SequenceMatcher(None, [t[0] for t in ot], [t[0] for t in nt], autojunk=False)
    ops = [o for o in sm.get_opcodes() if o[0] != "equal"]
    groups = []
    for o in ops:
        if groups and o[1] - groups[-1][2] < gap:
            groups[-1] = (groups[-1][0], groups[-1][1], o[2], groups[-1][3], o[4])
        else:
            groups.append(("x", o[1], o[2], o[3], o[4]))
    out = []
    for _, i1, i2, j1, j2 in groups:
        # 向左右扩 ctx 个「词」（标点不算）
        a, b, n = i1, j1, 0
        while a > 0 and n < ctx:
            a, b = a - 1, b - 1
            n += 1 if WORD.fullmatch(ot[a][0]) else 0
        c, d, n = i2, j2, 0
        while c < len(ot) and d < len(nt) and n < ctx:
            n += 1 if WORD.fullmatch(ot[c][0]) else 0
            c, d = c + 1, d + 1
        os_ = old[ot[a][1]:ot[c - 1][2]] if c > a else ""
        ns_ = new[nt[b][1]:nt[d - 1][2]] if d > b else ""
        out.append((os_, ns_))
    return out


TEXSP = re.compile(r"(?<!\\)([$%&#_])")


def _texesc(s):
    """文档里的 $ % & # _ 在 LaTeX 里要写成 \$ 等（11-15「\$1,500」被截成孤立反斜杠、编译失败）。"""
    return TEXSP.sub(r"\\\1", s)


def to_tex_edit(old_seg, new_seg, src, find_unique):
    for esc_ in (True, False):
        for mp in MAPS:
            o = _conv(old_seg, mp)
            if esc_:
                o2 = _texesc(o)
                if o2 == o:
                    continue  # 没有特殊字符，留给下面不转义那一轮
                o = o2
            a, b, how = find_unique(src, o)
            if a is not None and not (a > 0 and src[a - 1] == "\\") and not src[a:b].endswith("\\"):
                return {"tex_old": src[a:b], "tex_new": _texesc(_conv(new_seg, mp)), "how": how}
    return None


def iid(*parts):
    return "g-" + hashlib.sha1("\x00".join(parts).encode("utf-8")).hexdigest()[:10]


def compute(paras, comments, baseline, src, find_unique, locate):
    """返回 (items, new_baseline, lag)。items 每条含 kind: edit / need_lead / conflict / comment。"""
    seq, idx = tex_seq(src)
    items, lag = [], 0
    base = baseline or []
    trk = [p for p in paras if p["tracked"]]
    body = paras[1:]  # 第一段是标题（pandoc 把标题和作者并成一段），不比
    bbody = base[1:] if base else []

    def pair(i, p):
        if len(bbody) == len(body):
            return bbody[i]
        best, br = None, 0.0
        pw = WORD.findall(p["cur"].lower())
        for b in bbody:
            r = difflib.SequenceMatcher(None, pw, WORD.findall(b.lower()), autojunk=False).ratio()
            if r > br:
                best, br = b, r
        return best if br >= 0.5 else None

    def add_change(old, new, origin, conflict_why=None):
        for os_, ns_ in segments(old, new):
            t = to_tex_edit(os_, ns_, src, find_unique) if os_ else None
            loc = locate(os_ or new[:200], None)
            if not t and ns_ and to_tex_edit(ns_, ns_, src, find_unique):
                continue  # 新写法已在 LaTeX 里（已写回过）
            if not t and conflict_why:
                add_conflict(os_, ns_, conflict_why)
                continue
            if t and t["tex_old"] != t["tex_new"]:
                items.append({"id": iid("edit", t["tex_old"], t["tex_new"]), "kind": "edit", "origin": origin,
                              "old": t["tex_old"], "new": t["tex_new"], "plain_old": os_, "plain_new": ns_,
                              "why": f"Liang Hu 在 Google 文档{origin}", "line": loc["line"] if loc else None})
            elif not t:
                if ns_ and to_tex_edit(ns_, ns_, src, find_unique):
                    continue  # 新写法已在 LaTeX 里（已写回过）
                items.append({"id": iid("lead", os_, ns_), "kind": "need_lead", "origin": origin, "plain_old": os_,
                              "plain_new": ns_, "line": loc["line"] if loc else None,
                              "why": "这处含 LaTeX 格式（公式、引用、强调等）或找不到唯一位置，要请 Lead 转成源码修改"})

    def add_conflict(old, new, why):
        loc = locate(old or new, None)
        items.append({"id": iid("conflict", old, new), "kind": "conflict", "plain_old": old, "plain_new": new,
                      "line": loc["line"] if loc else None, "why": why})

    for p in trk:  # 建议修订：逐处看——原文还在 LaTeX → 待批；新写法已在 → 已写回，跳过；都不在 → 冲突
        add_change(p["old"], p["cur"], "的建议修订", conflict_why="Google 文档里建议修订的这处，Overleaf 里也已改过")
    clean = True
    for i, p in enumerate(body):
        if p["tracked"]:
            clean = False
            continue
        ok = aligned(p["cur"], seq, idx)
        if not base:
            if not ok:
                clean = False
                add_conflict("", p["cur"], "这段在 Google 文档里对不上 Overleaf，分不清是哪边改的")
            continue
        b = pair(i, p)
        if b == p["cur"]:
            if not ok:
                lag += 1  # Overleaf 后来改了，Google 文档还是旧的
                clean = False
            continue
        if b is not None and aligned(b, seq, idx):
            n0 = len(items)
            add_change(b, p["cur"], "里直接改的")
            if len(items) > n0:
                clean = False
            continue
        if ok:
            continue  # Google 文档改的和 Overleaf 现状一致（已写回或两边改成一样）
        clean = False
        add_conflict(b or "", p["cur"], "这段 Google 文档和 Overleaf 都改过" if b else "Google 文档里新出现的段落，对不上 Overleaf")
    new_baseline = [p["cur"] for p in paras] if (clean and not trk) else baseline
    for c in comments:
        loc = locate(c["anchor"], None) if c["anchor"] else None
        items.append({"id": iid("comment", c["cid"], c["anchor"], c["text"]), "kind": "comment", "plain_old": c["anchor"],
                      "comment": c["text"], "author": c["author"], "line": loc["line"] if loc else None, "why": "Google 文档批注"})
    return items, new_baseline, lag
