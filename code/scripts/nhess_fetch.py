"""L26.9 NHESS 取件：讨论稿 PDF、讨论页文本、RC/AC 独立 PDF 与补充 PDF（Copernicus 开放获取，CC BY）。
只写 ~/qt_sandbox/L26.9/nhess/H*/（不发布）。用法: python3 -I nhess_fetch.py <nhess_dir>"""
import sys, json, re, shutil, subprocess, hashlib, pathlib, urllib.request, time
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
def dl(url, f):
    if f.exists(): return True
    for k in range(4):
        r = _dl(url, f)
        if r != "retry": return r
        time.sleep(20 * (k + 1))
    return False
def _dl(url, f):
    time.sleep(3)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
            b = r.read()
        if not b.startswith(b"%PDF"): return False
        f.write_bytes(b); time.sleep(0.5); return True
    except Exception as e:
        if "404" in str(e): return False
        print("   dl err", url.rsplit("/",1)[1], str(e)[:60], flush=True); return "retry"
def txt(f): subprocess.run(["pdftotext", "-layout", str(f), str(f.with_suffix(".txt"))])
def main(nd):
    nd = pathlib.Path(nd); picks = json.loads((nd / "picks.json").read_text()); rows = []
    for p in picks:
        d = nd / p["paper"]; d.mkdir(exist_ok=True); pre = p["preprint"]
        base = (f"https://egusphere.copernicus.org/preprints/{pre[10:14]}/{pre}/" if pre.startswith("egusphere") else f"https://nhess.copernicus.org/preprints/{pre}/")
        src = nd / "cand" / (p["doi"].replace("/", "_") + ".txt"); shutil.copy(src, d / "discussion.txt")
        ok = dl(base + f"{pre}.pdf", d / "preprint.pdf")
        got = []
        names = [u.rsplit("/", 1)[1] for u in p.get("supplements", [])]
        if p["year"] < 2022:  # 旧版讨论页只列标题，正文在独立 PDF
            names += [f"{pre}-{k}{n}.pdf" for k in ("RC", "AC") for n in range(1, p["n_rc"] + 2)]
        for name in names:
            if dl(base + name, d / name): got.append(name)
        for f in d.glob("*.pdf"): txt(f)
        pages = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(d / "preprint.pdf")], capture_output=True, text=True).stdout).group(1)) if ok else None
        sha = hashlib.sha256((d / "preprint.pdf").read_bytes()).hexdigest() if ok else None
        rows.append(dict(paper=p["paper"], doi=p["doi"], preprint=pre, preprint_ok=ok, pages=pages, preprint_sha256=sha, files=got))
        print(p["paper"], pre, ok, pages, got, flush=True)
    (nd / "fetch_log.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
if __name__ == "__main__": main(sys.argv[1])
