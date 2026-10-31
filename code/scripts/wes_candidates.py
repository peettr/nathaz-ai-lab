"""L26.9 WES 候选检索：Crossref 每层关键词前 40 条 → 抓讨论页 → 统计 RC 数与词数。只读公开网页。
用法: python3 -I wes_candidates.py <out_dir>"""
import sys, json, re, html, time, urllib.request, urllib.parse, pathlib
STRATA = {
 "S1": "wind farm wake", "S2": "large-eddy simulation atmospheric boundary layer",
 "S3": "lidar inflow turbulence measurement", "S4": "extreme wind gust storm",
 "S5": "wind resource climate statistics", "S6": "blade aerodynamics aeroelastic loads",
 "S7": "floating offshore wind turbine dynamics", "S8": "wind tunnel experiment model turbine"}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36", "Accept": "text/html"}
def get(url, t=30, api=False):
    h = {"User-Agent": "L26.9-quicktrial (mailto:none)"} if api else UA
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=t) as r: return r.read().decode("utf-8", "replace")
def totext(s):
    s = re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S)
    s = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", s)
    return re.sub(r"\n\s*\n+", "\n", html.unescape(re.sub(r"<[^>]+>", "", s)))
def rc_blocks(txt):
    heads = list(re.finditer(r"^\s*(RC|AC|CC|EC)(\d+):\s+(.*)$", txt, re.M))
    out = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else txt.find("AR: Author's response")
        body = txt[h.end(): end if end > 0 else None]
        body = body.split("Citation: https://doi.org")[0]
        out.append({"kind": h.group(1), "n": int(h.group(2)), "title": h.group(3).strip(), "words": len(body.split())})
    return out
def main(od):
    od = pathlib.Path(od); od.mkdir(parents=True, exist_ok=True); rows = []
    for s, q in STRATA.items():
        u = "https://api.crossref.org/works?" + urllib.parse.urlencode({"query.bibliographic": q, "filter": "issn:2366-7451,type:journal-article,from-pub-date:2017-01-01,until-pub-date:2025-12-31", "rows": 25, "select": "DOI,title,published"})
        items = json.loads(get(u, 60, api=True))["message"]["items"]
        for it in items:
            doi = it["DOI"]; m = re.match(r"10\.5194/wes-(\d+)-(\d+)-(\d+)$", doi)
            if not m: continue
            v, p, y = m.groups()
            cache = od / (doi.replace("/", "_") + ".json")
            if cache.exists():
                rows.append(dict(json.loads(cache.read_text()), stratum=s)); continue
            durl = f"https://wes.copernicus.org/articles/{v}/{p}/{y}/wes-{v}-{p}-{y}-discussion.html"
            try:
                raw = get(durl); txt = totext(raw)
            except Exception as e:
                rows.append({"stratum": s, "doi": doi, "err": str(e)[:80]}); continue
            pre = re.search(r"preprints/(wes-\d{4}-\d+)", raw)
            bl = rc_blocks(txt); rcs = [b for b in bl if b["kind"] == "RC"]
            sup = sorted(set(re.findall(r'href="([^"]*-RC\d+-supplement\.pdf)"', raw)))
            rows.append({"stratum": s, "doi": doi, "year": int(y), "title": it["title"][0], "preprint": pre.group(1) if pre else None,
                         "n_rc": len(rcs), "rc_words_inline": sum(b["words"] for b in rcs), "rc_supplements": sup, "discussion_url": durl})
            (od / f"{doi.replace('/', '_')}.txt").write_text(txt)
            cache.write_text(json.dumps(rows[-1], ensure_ascii=False))
            time.sleep(0.5)
        print(s, len(items), flush=True)
        (od / "candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    (od / "candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
if __name__ == "__main__": main(sys.argv[1])
