"""L26.9 盲化：把各份审稿意见统一成纯编号条目、删去轴名、打乱、换随机编号。
用法: python3 -I blind.py <reports_dir> <out_dir> <seed>
reports_dir 下每份文件名形如 <paper>__<arm>__<run>.md；输出 out_dir/<paper>_items.jsonl 与 blind_key.json（判完前不打开）。"""
import sys, re, json, random, hashlib, pathlib
AXES = ["novelty-significance","mechanism-evidence","experimental-design","statistical-rigor","reproducibility",
        "clinical-validity","ethical-governance","data-resource-quality","figures-and-tables","writing-clarity",
        "claim-moderation","mechanistic-vs-correlative"]
AXIS_RE = re.compile("|".join(re.escape(a) for a in AXES) + r"|逐(一|项)?检查|检查(清单|轴)|方面\s*\d+", re.I)
ITEM_RE = re.compile(r"^\s*(?:\d+[\.\)、]|[-*])\s+(.*)")
NUM_RE = re.compile(r"^\d+[\.\)、]\s+(.*)")
def items(text):
    # 10-21 修订（第 3 批判定前）：稿中有编号条目时，只有顶格编号行开新条目，子弹点并入当前条目
    numbered = any(NUM_RE.match(l) for l in text.splitlines())
    out, cur = [], None
    for line in text.splitlines():
        m = NUM_RE.match(line) if numbered else ITEM_RE.match(line)
        if m:
            if cur: out.append(cur)
            cur = m.group(1).strip()
        elif cur is not None and line.strip():
            cur += " " + line.strip()
    if cur: out.append(cur)
    return [AXIS_RE.sub("", i).strip(" :：-") for i in out]
def main(src, dst, seed):
    rng = random.Random(int(seed)); dst = pathlib.Path(dst); dst.mkdir(parents=True, exist_ok=True)
    key, by_paper = {}, {}
    for f in sorted(pathlib.Path(src).glob("*__*__*.md")):
        paper, arm, run = f.stem.split("__")
        for k, it in enumerate(items(f.read_text())):
            by_paper.setdefault(paper, []).append((arm, run, k, it))
    for paper, rows in by_paper.items():
        rng.shuffle(rows)
        with open(dst / f"{paper}_items.jsonl", "w") as fo:
            for arm, run, k, it in rows:
                bid = f"{paper}-{rng.getrandbits(32):08x}"
                key[bid] = {"arm": arm, "run": run, "orig_idx": k}
                fo.write(json.dumps({"id": bid, "text": it}, ensure_ascii=False) + "\n")
    kp = dst / "blind_key.json"; kp.write_text(json.dumps(key, ensure_ascii=False, indent=0))
    print("blind_key sha256", hashlib.sha256(kp.read_bytes()).hexdigest())
if __name__ == "__main__": main(*sys.argv[1:4])
