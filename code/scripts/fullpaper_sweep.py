#!/usr/bin/env python3
"""Read-only full-PDF lexical candidate sweep. This is NOT human full reading/truth."""
import csv,json,re,subprocess,time
from pathlib import Path
R=Path(__file__).resolve().parent.parent
keys=['36XAQH9L','NXSSET4J','WZN3ETI3','8IC5IFK5','UT8ZUPS5','6X6ZP3YD','R5RKQGYZ','GBK98YNH']
rows={r['key']:r for r in csv.DictReader((R/'downburst_profiles_sample_v2.csv').open())}
pat=re.compile(r'(?i)(?:z\s*[_−-]?\s*max|u\s*[_−-]?\s*max|v\s*[_−-]?\s*max|r\s*/\s*d|figure\s*\d+|fig\.\s*\d+|wood|vicroy|oseguera|velocity profile|wind speed profile|竖向廓线|最大风速)')
res=[]
for key in keys:
 row=rows[key];t=time.monotonic();r=subprocess.run(['pdftotext','-layout',row['pdf'],'-'],capture_output=True,timeout=100)
 if r.returncode and not r.stdout:res.append(dict(key=key,error=r.stderr.decode(errors='replace')[:250]));continue
 pages=r.stdout.decode('utf8',errors='replace').split('\f'); pages=pages[:-1] if not pages[-1].strip() else pages
 hits=[]
 for p,txt in enumerate(pages,1):
  for m in pat.finditer(txt):
   hits.append(dict(page=p,term=m.group(),context=re.sub(r'\s+',' ',txt[max(0,m.start()-90):m.end()+170])))
 res.append(dict(key=key,total_physical_pages=len(pages),target_page=int(row['page']),candidate_occurrences=len(hits),candidate_pages=sorted(set(h['page'] for h in hits)),elapsed_seconds=round(time.monotonic()-t,2),sample_candidates=hits[:12]))
 print(key,len(pages),'candidates',len(hits),'sec',round(time.monotonic()-t,2),flush=True)
out=R/'fullpaper_candidate_sweep.jsonl'
with out.open('x') as f:
 for x in res:f.write(json.dumps(x,ensure_ascii=False)+'\n')
print(out)
