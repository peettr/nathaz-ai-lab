"""L26.9 NHESS 选样：按 选样规则_NHESS_20261026.md 过滤与抽取。
步骤 list：列出每层 RC≥2 的候选（含标题），供 Lead 按标题判层（写 title_excl.json：{层: [doi…]} 为剔除）。
步骤 draw：对剩余候选补 RC 补充 PDF 词数，过滤 ≥400 词，按种子 20261026 每层抽序（输出各层顺位，供逐个查页数）。
用法: python3 -I nhess_select.py list|draw <cand_dir>"""
import sys, json, random, pathlib, subprocess, urllib.request
STR = [f"N{i}" for i in range(1, 11)]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
def sup_words(url, cd):
    f = cd / "sup" / url.rsplit("/", 1)[1]; f.parent.mkdir(exist_ok=True)
    if not f.exists():
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r: f.write_bytes(r.read())
    t = subprocess.run(["pdftotext", str(f), "-"], capture_output=True, text=True).stdout
    return len(t.split())
def main(step, cd):
    cd = pathlib.Path(cd); rows = json.loads((cd / "candidates.json").read_text())
    by = {s: [r for r in rows if r["stratum"] == s and r.get("n_rc", 0) >= 2 and "err" not in r] for s in STR}
    if step == "list":
        for s in STR:
            print(f"## {s}  (候选 {sum(1 for r in rows if r['stratum']==s)}，RC≥2 {len(by[s])})")
            for r in by[s]: print(f"  {r['doi']} {r['year']} RC{r['n_rc']} w{r['rc_words_inline']} | {r['title'][:110]}")
        return
    incl = json.loads((cd / "title_incl.json").read_text()); rng = random.Random(20261026); out = {}
    allrows = {r["doi"]: r for r in rows if r.get("n_rc", 0) >= 2 and "err" not in r}
    def words(r):
        w = r["rc_words_inline"] + sum(sup_words(u, cd) for u in r.get("supplements", []) if "-RC" in u)
        if r["rc_words_inline"] < 50 and r.get("preprint"):
            base = (f"https://egusphere.copernicus.org/preprints/20{r['preprint'][10:12]}/{r['preprint']}/" if r["preprint"].startswith("egusphere")
                    else f"https://nhess.copernicus.org/preprints/{r['preprint']}/")
            for n in range(1, r["n_rc"] + 1):
                try: w += sup_words(base + f"{r['preprint']}-RC{n}.pdf", cd)
                except Exception as e: print("  no RC pdf", r["doi"], n, str(e)[:40])
        return w
    for s in STR:
        ok = []
        for d in incl.get(s, []):
            r = allrows.get(d)
            if not r: continue
            w = words(r)
            if w >= 400: ok.append(dict(r, stratum=s, rc_words=w))
        ok.sort(key=lambda r: r["doi"]); rng.shuffle(ok); out[s] = ok
        print(s, len(ok), [(r["doi"], r["year"], r["rc_words"]) for r in ok])
    pool = sorted(set(sum((incl[s] for s in STR), [])) | set(incl.get("_pool_extra", [])))
    pool_ok = []
    for d in pool:
        r = allrows.get(d)
        if r:
            w = words(r)
            if w >= 400: pool_ok.append(dict(r, rc_words=w))
    rng.shuffle(pool_ok); out["_pool"] = pool_ok
    print("_pool", len(pool_ok), [(r["doi"], r["rc_words"]) for r in pool_ok])
    (cd / "draw_order.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
if __name__ == "__main__": main(*sys.argv[1:3])
