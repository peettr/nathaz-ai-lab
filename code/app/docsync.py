"""L26.25 · Google 文档为主稿：把 Liang Hu 在文档（Drive 里的 docx）里的直接修改按段同步回 LaTeX。

plan(src, paras, baseline) → 动作列表；每个动作只改 LaTeX 的一个段（unit），由调用方逐条写入、编译检查、提交。
- 段对齐：LaTeX 正文按空行/\\item/标题切成段，与 docx 段落（建议模式的修改按「未接受」算，即只取原文）按文字对齐。
- 方向：baseline＝上次同步完成时文档各段文字。文档段不在 baseline 里＝Liang Hu 改过→以文档为准写进 LaTeX；
  文档段还是 baseline 里的、LaTeX 却不同＝LaTeX 这边改的→不动，记「同步异常」。
- 写法：先逐词定点改（保住 \\cite、公式等标记）；不行且该段只有简单格式（无公式/引用/环境）→整段换成文档写法；否则记「同步异常」。
"""
import difflib, re
from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
q = lambda t: "{%s}%s" % (W, t)
HARD = re.compile(r"\\(cite\w*|ref|eqref|autoref|footnote|begin|end|includegraphics|input|include)\b|\$|\\\[|\\\(")


# ---------- 归一（只用于比较） ----------
def norm(s):
    s = s.replace("\u00a0", " ").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("—", "--").replace("–", "-")
    return " ".join(s.split())


def tex_plain(t):
    t = re.sub(r"\\label\{[^{}]*\}", "", t)
    t = re.sub(r"\\href\{[^{}]*\}\{([^{}]*)\}", r"\1", t)
    for _ in range(3):
        t = re.sub(r"\\(emph|textit|textbf|textsc|underline|textrm|mbox|url)\{([^{}]*)\}", r"\2", t)
    t = re.sub(r"\\(cite\w*|ref|eqref)\{[^{}]*\}", "", t)
    for a, b in (("\\ldots{}", "…"), ("\\ldots", "…"), ("---", "—"), ("--", "–"), ("``", "“"), ("''", "”"), ("`", "‘"), ("~", " "),
                 ("\\%", "%"), ("\\&", "&"), ("\\_", "_"), ("\\#", "#"), ("\\$", "$"), ("{}", ""), ("\\\\", " ")):
        t = t.replace(a, b)
    return " ".join(t.replace("'", "’").split())


def wsim(a, b):
    """按单词的相似度（Dice），公式/引用记号影响小，用于段落配对。"""
    from collections import Counter
    A = Counter(re.findall(r"[a-z]{2,}", norm(a).lower()))
    B = Counter(re.findall(r"[a-z]{2,}", norm(b).lower()))
    n = sum(A.values()) + sum(B.values())
    return 2 * sum((A & B).values()) / n if n else 1.0


# ---------- LaTeX 切段 ----------
def latex_units(src):
    """返回正文的段：{a,b（在 src 中的字符区间）, kind: para|item|heading|skip, body_a/body_b（可替换文字区间）, plain}。
    逐行判断：空行分段；小节标题（可跨行、可带 \\label 行）、环境（整体跳过）、列表项、控制行各自成段。"""
    m0 = src.find("\\begin{document}")
    m1 = src.find("\\end{document}")
    if m0 < 0:
        return []
    pos = src.find("\n", m0) + 1
    lines = []
    for ln in src[pos:m1].split("\n"):
        lines.append((pos, pos + len(ln), ln))
        pos += len(ln) + 1
    units, cur = [], []

    def emit(kind, ls, body=None):
        if not ls:
            return
        a, b = ls[0][0], ls[-1][1]
        u = {"a": a, "b": b, "kind": kind, "plain": ""}
        if body:
            u["body_a"], u["body_b"] = body
            u["plain"] = tex_plain(src[body[0]:body[1]])
        units.append(u)

    def flush():
        if cur:
            emit(cur[0][3], [x[:3] for x in cur], (cur[0][4], cur[-1][1]))
            cur.clear()

    i = 0
    while i < len(lines):
        a, b, ln = lines[i]
        s = ln.strip()
        if not s:
            flush(); i += 1; continue
        m = re.match(r"\s*\\((?:sub)*section)\*?\{", ln)
        if m:
            flush()
            ta = a + m.end()
            depth, k = 1, ta
            j = i
            while depth and j < len(lines):
                lb = lines[j][1]
                while k < lb and depth:
                    depth += {"{": 1, "}": -1}.get(src[k], 0)
                    k += 1
                if depth:
                    j += 1
                    if j < len(lines):
                        k = lines[j][0]
            ls = lines[i:j + 1]
            if j + 1 < len(lines) and re.match(r"\s*\\label\{[^{}]*\}\s*$", lines[j + 1][2]):
                ls = lines[i:j + 2]; j += 1
            emit("heading", ls, (ta, k - 1))
            i = j + 1; continue
        m = re.match(r"\s*\\begin\{(\w+\*?)\}", ln)
        if m:
            flush()
            env = m.group(1)
            if env in ("itemize", "enumerate", "description"):
                emit("skip", [lines[i]]); i += 1; continue
            j = i
            while j < len(lines) and not re.search(r"\\end\{" + re.escape(env) + r"\}", lines[j][2]):
                j += 1
            emit("skip", lines[i:j + 1]); i = j + 1; continue
        if re.match(r"\s*\\end\{", ln) or re.match(r"\s*(%|\\(def|tightlist|setlength|renewcommand|newcommand|label|maketitle|newgeometry|vspace|noindent|centering|bibliography\w*|clearpage|newpage|appendix)\b|\{\\)", ln):
            flush(); emit("skip", [lines[i]]); i += 1; continue
        m = re.match(r"\s*\\item\b\s*", ln)
        if m:
            flush()
            cur.append((a, b, ln, "item", a + m.end())); i += 1; continue
        if not cur:
            cur.append((a, b, ln, "para", a))
        else:
            cur.append((a, b, ln, cur[0][3], cur[0][4]))
        i += 1
    flush()
    return units


# ---------- docx 段落 → LaTeX ----------
ESC = [("\\", "\\textbackslash{}"), ("&", "\\&"), ("%", "\\%"), ("$", "\\$"), ("#", "\\#"), ("_", "\\_"), ("{", "\\{"), ("}", "\\}"),
       ("^", "\\^{}"), ("~", "\\textasciitilde{}")]


def esc(t):
    out = []
    for ch in t:
        r = ch
        for a, b in ESC:
            if ch == a:
                r = b
                break
        out.append(r)
    t = "".join(out)
    for a, b in (("“", "``"), ("”", "''"), ("‘", "`"), ("’", "'"), ("\u00a0", "~"), ("—", "---"), ("–", "--"), ("…", "\\ldots{}")):
        t = t.replace(a, b)
    return t


def _on(rpr, tag):
    if rpr is None:
        return False
    e = rpr.find(q(tag))
    return e is not None and e.get(q("val")) not in ("0", "false")


def para_latex(p):
    """docx 段落（建议模式的插入不算、删除算原文）→ LaTeX 文字；斜体→\\emph，粗体→\\textbf。"""
    segs = []
    for r in p.iter(q("r")):
        if not _visible(r, p):
            continue
        txt = "".join((x.text or "") for x in r if x.tag in (q("t"), q("delText")))
        if not txt:
            continue
        rpr = r.find(q("rPr"))
        segs.append([txt, _on(rpr, "i"), _on(rpr, "b")])
    merged = []
    for s in segs:
        if merged and merged[-1][1:] == s[1:]:
            merged[-1][0] += s[0]
        else:
            merged.append(s)
    out = []
    for t, it, bd in merged:
        lead = t[:len(t) - len(t.lstrip())]
        trail = t[len(t.rstrip()):]
        core = esc(t.strip())
        if core and it:
            core = "\\emph{" + core + "}"
        if core and bd:
            core = "\\textbf{" + core + "}"
        out.append(esc(lead) + core + esc(trail) if core else esc(t))
    return "".join(out).strip()


# 11-16 Liang Hu：在文档里用建议模式（修订）改的，默认算已接受——和 Word 修订的用法一样，痕迹留在文档里，但主稿文字按「全部接受」算。
# Lead/工作台自己写进文档的修订不算（仍按未接受）。ACCEPT_TRACKED=False 回到旧做法（全部拒绝视图）。
ACCEPT_TRACKED = True
LEAD_AUTHORS = ("Lead", "Research Chat Lead", "L26.25 工作台")


def _track(r, p):
    """run 所在的修订：('ins'|'del'|None, 作者)；在文本框里返回 ('box', '')。"""
    anc = r.getparent()
    while anc is not None and anc is not p:
        if anc.tag == q("txbxContent"):
            return "box", ""
        if anc.tag in (q("ins"), q("del")):
            return ("ins" if anc.tag == q("ins") else "del"), anc.get(q("author")) or ""
        anc = anc.getparent()
    return None, ""


def _visible(r, p):
    k, au = _track(r, p)
    if k == "box":
        return False
    if not ACCEPT_TRACKED or au in LEAD_AUTHORS:
        return k != "ins"   # 拒绝视图：插入不算、删除算原文
    return k != "del"       # 接受视图：插入算、删除不算


def para_plain(p):
    return "".join(x.text or "" for r in p.iter(q("r")) if _visible(r, p) for x in r if x.tag in (q("t"), q("delText")))


def _in_ins(r, p):
    anc = r.getparent()
    while anc is not None and anc is not p:
        if anc.tag in (q("ins"), q("txbxContent")):
            return True
        anc = anc.getparent()
    return False


def docx_body_paras(doc_xml_bytes):
    """docx 正文段落（不含文本框里的），从第一个标题段开始（前面的标题块不比）。"""
    root = etree.fromstring(doc_xml_bytes)
    body = root.find(q("body"))
    out = []
    for p in body.iter(q("p")):
        if any(a.tag in (q("txbxContent"), q("tbl")) for a in p.iterancestors()):
            continue  # 文本框、表格里的段落不比（LaTeX 里表格/环境整体跳过）
        t = para_plain(p)
        if not t.strip():
            continue
        st = p.find(f"{q('pPr')}/{q('pStyle')}")
        style = st.get(q("val")) if st is not None else ""
        if re.search(r"(?i)caption", style):
            continue  # 图表标题在 LaTeX 的 figure/table 环境里，跳过
        out.append({"el": p, "text": t, "style": style, "heading": bool(re.match(r"(?i)heading", style))})
    return out


# ---------- 计划 ----------
def plan(src, dparas, baseline, max_actions=40, force=(), base_tex=(), revert=(), protect=()):
    """返回 (actions, issues)。actions: {kind: word|replace|insert|delete, unit, new_text, ...}；issues: 同步异常。"""
    from gdoc import segments, to_tex_edit
    units = [u for u in latex_units(src) if u["kind"] != "skip"]
    k0 = next((i for i, u in enumerate(units) if u["kind"] == "heading"), 0)
    units = units[k0:]
    if units:  # 文档从第一个与 LaTeX 第一个标题对得上的段落开始（前面的标题、作者、摘要块不比）
        h0 = norm(units[0]["plain"])
        j0 = next((j for j, p in enumerate(dparas) if norm(p["text"]) == h0), None)
        if j0 is None:
            return [], [{"why": "Google 文档里找不到与 LaTeX 第一个小节标题对应的段落，暂停自动同步，请 Lead 核对", "line": None, "doc": units[0]["plain"][:100]}]
        dparas = dparas[j0:]
    base = set(norm(x) for x in (baseline or []))
    btex = set(base_tex or ())
    L = [norm(u["plain"]) for u in units]
    D = [norm(p["text"]) for p in dparas]
    sm = difflib.SequenceMatcher(None, L, D, autojunk=False)
    actions, issues = [], []

    def find_unique(text, old):
        n = text.count(old)
        if n == 1:
            i = text.index(old)
            return i, i + len(old), "精确"
        if n > 1:
            return None, n, "定位不唯一"
        toks = old.split()
        if not toks:
            return None, 0, "原句为空"
        ms = list(re.finditer(r"\s+".join(re.escape(t) for t in toks), text))
        if len(ms) == 1:
            return ms[0].start(), ms[0].end(), "空白归一"
        return None, len(ms), "找不到"

    def doc_changed(dp):
        return not base or norm(dp["text"]) not in base

    def change(u, dp):
        if not doc_changed(dp) and not any(f and f in norm(u["plain"]) for f in force):
            if norm(u["plain"]) in btex:
                return  # 两边都没变：只是 LaTeX 与 docx 的写法换算差异（公式、引用等），不算异常
            issues.append({"why": "Overleaf 里这段与 Google 文档不同，但文档这段没改过（可能是有人直接改了 LaTeX）；未回改，请 Lead 核对",
                           "line": src[:u["a"]].count("\n") + 1, "doc": dp["text"][:300]})
            return
        seg_src = src[u["body_a"]:u["body_b"]]
        if norm(tex_plain(seg_src)) == norm(dp["text"]):
            return  # LaTeX 这段已经与文档一致（防止同一处变化被重复套用，11-15 重复插句事故）
        # 有基线时：只把「文档相对上次同步」的变化逐处套到 LaTeX；已经在 LaTeX 里的变化（如 Lead 建议同步进文档的）跳过——按内容去重，防循环
        bp = None
        if baseline:
            cands = [(difflib.SequenceMatcher(None, norm(b), norm(dp["text"]), autojunk=False).ratio(), b) for b in baseline]
            r, b = max(cands) if cands else (0, None)
            bp = b if r >= 0.5 else None
        if bp is not None and norm(bp) != norm(dp["text"]):
            # 第 2 条：这段里有「已接受、但被 Liang Hu 在文档里改写」的 Lead 改动 → 先在 LaTeX 里还原它，再套 Liang Hu 的变化
            work, reverted = seg_src, False
            for tn, to in revert:
                if tn and tn in work:
                    work, reverted = work.replace(tn, to, 1), True
            for ctx in (3, 2, 1):  # 上下文跨过引用/公式时，缩小上下文再试
                new_seg, ok, n = work, True, 0
                for os_, ns_ in reversed(segments(bp, dp["text"], ctx=ctx)):
                    if ns_ and ns_ != os_ and len(ns_) > len(os_) and os_ in ns_ and to_tex_edit(ns_, ns_, new_seg, find_unique):
                        continue  # 纯新增且新写法 LaTeX 里已有 → 已同步过，不再追加（11-15 段尾同一句被插 13 遍）
                    t = to_tex_edit(os_, ns_, new_seg, find_unique) if os_ else None
                    if t:
                        new_seg = new_seg.replace(t["tex_old"], t["tex_new"], 1)
                        n += 1
                    elif ns_ and to_tex_edit(ns_, ns_, new_seg, find_unique):
                        continue  # 这处变化 LaTeX 里已经有了（如 Lead 建议同步进文档的）
                    else:
                        ok = False
                        break
                if ok:
                    if n and not reverted and wsim(tex_plain(new_seg), dp["text"]) < wsim(tex_plain(seg_src), dp["text"]):
                        issues.append({"why": "按文档改动套到 LaTeX 后反而离文档更远（可能重复插入），已停下未改；请 Lead 按文档核对这段",
                                       "line": src[:u["a"]].count("\n") + 1, "doc": dp["text"][:300]})
                        return
                    if n or reverted:
                        actions.append({"kind": "word", "unit": u, "new_text": new_seg, "doc": dp["text"]})
                    return
        if HARD.search(seg_src):  # 没有基线可比时，含公式/引用的段不敢逐词对齐（会把公式当成多余文字删掉）
            issues.append({"why": "这段含公式/引用/环境，Google 文档里有改动但不能自动对回 LaTeX；请 Lead 按文档把 LaTeX 改成一致", "line": src[:u["a"]].count("\n") + 1, "doc": dp["text"][:300]})
            return
        new_seg, ok = seg_src, True
        for os_, ns_ in reversed(segments(u["plain"], dp["text"])):
            t = to_tex_edit(os_, ns_, new_seg, find_unique) if os_ else None
            if not t:
                ok = False
                break
            new_seg = new_seg.replace(t["tex_old"], t["tex_new"], 1)
        if ok and norm(tex_plain(new_seg)) == norm(dp["text"]):
            actions.append({"kind": "word", "unit": u, "new_text": new_seg, "doc": dp["text"]})
            return
        if HARD.search(seg_src):
            issues.append({"why": "这段含公式/引用/环境，不能整段替换；请 Lead 按 Google 文档把 LaTeX 改成一致", "line": src[:u["a"]].count("\n") + 1, "doc": dp["text"][:300]})
            return
        if u["kind"] == "heading":
            actions.append({"kind": "replace", "unit": u, "new_text": esc(dp["text"].strip()), "doc": dp["text"]})
        else:
            actions.append({"kind": "replace", "unit": u, "new_text": para_latex(dp["el"]), "doc": dp["text"]})

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        Ls, Ds = list(range(i1, i2)), list(range(j1, j2))
        pairs = []
        while Ls and Ds:  # 按相似度两两配对
            best = max(((wsim(units[a]["plain"], dparas[b]["text"]), a, b) for a in Ls for b in Ds))
            if best[0] < 0.5:
                break
            pairs.append((best[1], best[2]))
            Ls.remove(best[1])
            Ds.remove(best[2])
        for a, b in sorted(pairs):
            change(units[a], dparas[b])
        for b in Ds:  # 文档里有、LaTeX 里没有
            dp = dparas[b]
            if baseline and max([wsim(x, dp["text"]) for x in baseline] or [0]) >= 0.6:
                issues.append({"why": "Google 文档里这段改过，但在 Overleaf 里找不到对应的段（没敢新增，免得重复）；请 Lead 核对", "line": None, "doc": dp["text"][:300]})
                continue
            if any(wsim(u["plain"], dp["text"]) >= 0.6 for u in units):
                issues.append({"why": "Google 文档里这段与 Overleaf 某段很像但没对上（没敢新增，免得重复）；请 Lead 核对", "line": None, "doc": dp["text"][:300]})
                continue
            if not doc_changed(dp):
                issues.append({"why": "Google 文档里这段在 Overleaf 里没有了（可能有人直接删了 LaTeX）；未补回，请 Lead 核对", "line": None, "doc": dp["text"][:300]})
                continue
            prev = max([a for a, bb in pairs if bb < b] + [i1 - 1]) if (pairs or i1 > 0) else -1
            anchor = units[prev] if prev >= 0 else None
            kind = "item" if (anchor and anchor["kind"] == "item" and re.search(r"(?i)list", dp["style"])) else "para"
            actions.append({"kind": "insert", "after": anchor, "new_text": ("\\item " if kind == "item" else "") + para_latex(dp["el"]), "doc": dp["text"], "item": kind == "item"})
        for a in Ls:  # LaTeX 里有、文档里没有
            u = units[a]
            if base and norm(u["plain"]) in base and u["kind"] in ("para", "item") and not HARD.search(src[u["a"]:u["b"]]):
                actions.append({"kind": "delete", "unit": u, "doc": ""})
            else:
                issues.append({"why": "Overleaf 里这段在 Google 文档里没有；" + ("首次同步不自动删" if not base else "可能是 LaTeX 新加的") + "，请 Lead 核对",
                               "line": src[:u["a"]].count("\n") + 1, "doc": u["plain"][:300]})
    # 11-16 规则：已接受、但从没进过文档的内容（protect）不能因「文档为主稿」被从 LaTeX 改掉或删掉；只有文档里有过、后来没了才算删除
    if protect:
        keep = []
        for a in actions:
            u = a.get("unit")
            if u is None or a["kind"] == "insert":
                keep.append(a)
                continue
            before = norm(u["plain"])
            after = "" if a["kind"] == "delete" else norm(tex_plain(a["new_text"]))
            lost = [f for f in protect if f and f in before and f not in after]
            if lost:
                issues.append({"why": "这段里有已接受、但还没进 Google 文档的 Lead 改动；按规则不从 LaTeX 删，未改这段。请 Lead 先把它补进文档",
                               "line": src[:u["a"]].count("\n") + 1, "doc": lost[0][:300]})
            else:
                keep.append(a)
        actions = keep
    if len(actions) > max_actions:
        return [], issues + [{"why": f"这次要改 {len(actions)} 段，超过安全上限 {max_actions}，暂停自动同步，请 Lead 人工核对", "line": None, "doc": ""}]
    return actions, issues


def tex_units_plain(src):
    return [norm(u["plain"]) for u in latex_units(src) if u["kind"] != "skip"]


def apply(src, act):
    """把一个动作应用到 LaTeX 全文，返回新全文。"""
    if act["kind"] in ("word", "replace"):
        u = act["unit"]
        return src[:u["body_a"]] + act["new_text"] + src[u["body_b"]:]
    if act["kind"] == "delete":
        u = act["unit"]
        a, b = u["a"], u["b"]
        while b < len(src) and src[b] == "\n" and b - u["b"] < 1:
            b += 1
        return src[:a] + src[b:]
    if act["kind"] == "insert":
        anc = act["after"]
        pos = anc["b"] if anc else src.find("\n", src.find("\\begin{document}")) + 1
        sep = "\n" if act.get("item") else "\n\n"
        return src[:pos] + sep + act["new_text"] + src[pos:]
    return src
