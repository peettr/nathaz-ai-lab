"""L26.9 NHESS 候选检索：Crossref 每层关键词前 25 条 → 抓讨论页 → RC 数与页内词数。只读公开网页。
与 ../../scripts/wes_candidates.py 同法，改 ISSN、层与 URL。用法: python3 -I nhess_candidates.py <out_dir>"""
import sys, json, re, time, urllib.parse, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "scripts"))
from wes_candidates import get, totext, rc_blocks
STRATA = {"N1": "windstorm extratropical cyclone damage", "N2": "tropical cyclone typhoon wind hazard",
 "N3": "convective wind gust thunderstorm downburst", "N4": "tornado",
 "N5": "extreme wind speed return period gust statistics", "N6": "wind damage buildings vulnerability loss model",
 "N7": "windthrow forest storm damage", "N8": "windstorm insurance loss",
 "N9": "climate change windstorm projection", "N10": "wind hazard infrastructure power transmission"}
def main(od):
    od = pathlib.Path(od); od.mkdir(parents=True, exist_ok=True); rows = []
    for s, q in STRATA.items():
        u = "https://api.crossref.org/works?" + urllib.parse.urlencode({"query.bibliographic": q, "filter": "issn:1684-9981,type:journal-article,from-pub-date:2006-01-01,until-pub-date:2025-12-31", "rows": 25, "select": "DOI,title,published"})
        for k in range(8):
            try: items = json.loads(get(u, 60, api=True))["message"]["items"]; break
            except Exception as e:
                print(s, "crossref retry", k, str(e)[:60], flush=True); time.sleep(30 * (k + 1))
        else: raise SystemExit("crossref failed " + s)
        for it in items:
            doi = it["DOI"].lower(); m = re.match(r"10\.5194/nhess-(\d+)-(\d+)-(\d+)$", doi)
            if not m: continue
            v, p, y = m.groups(); cache = od / (doi.replace("/", "_") + ".json")
            if cache.exists():
                rows.append(dict(json.loads(cache.read_text()), stratum=s)); continue
            durl = f"https://nhess.copernicus.org/articles/{v}/{p}/{y}/nhess-{v}-{p}-{y}-discussion.html"
            try:
                raw = get(durl); txt = totext(raw)
            except Exception as e:
                r = {"stratum": s, "doi": doi, "year": int(y), "title": it["title"][0], "err": str(e)[:80]}
                rows.append(r); cache.write_text(json.dumps(r, ensure_ascii=False)); continue
            pre = re.search(r"preprints/(?:\d{4}/)?((?:nhess|egusphere)-\d{4}-\d+)", raw)
            pre_pdf = re.search(r'href="(https://[^"]*/preprints/[^"]*/(?:nhess|egusphere)-\d{4}-\d+\.pdf)"', raw)
            bl = rc_blocks(txt); rcs = [b for b in bl if b["kind"] == "RC"]
            sup = sorted(set(re.findall(r'href="([^"]*-(?:RC|AC)\d+-supplement\.pdf)"', raw)))
            rows.append({"stratum": s, "doi": doi, "year": int(y), "title": it["title"][0], "preprint": pre.group(1) if pre else None,
                         "preprint_pdf": pre_pdf.group(1) if pre_pdf else None, "n_rc": len(rcs),
                         "rc_words_inline": sum(b["words"] for b in rcs), "supplements": sup, "discussion_url": durl})
            (od / f"{doi.replace('/', '_')}.txt").write_text(txt); cache.write_text(json.dumps(rows[-1], ensure_ascii=False))
            time.sleep(0.5)
        print(s, len(items), flush=True)
        (od / "candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
if __name__ == "__main__": main(sys.argv[1])
