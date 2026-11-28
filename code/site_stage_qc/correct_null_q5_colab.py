"""Correct only the Q5 'no ISD record' carry-forward bug, before valid pairing.
Keep the first QC and failed NaN scoring artifacts immutable in parent directory.
"""
import json,csv,re,shutil,datetime as dt
from pathlib import Path
src=Path('/content/site_stage_qc');dst=src/'corrected';dst.mkdir(exist_ok=False)
def edt():return dt.datetime.now(dt.timezone(dt.timedelta(hours=-4))).isoformat()
rows=[]
for line in (src/'qc_station_seasons.jsonl').open():
 r=json.loads(line);p=r.get('qc_peak')
 if p and p['isd_status']=='ISD 未核' and p['kn'] is None:
  # Candidate field was integer except if Q2 reparsed from the matching raw report.
  v=p['original_kn'];raw=p['raw'].upper()
  if v!=int(v):
   if p['source']=='pk':m=re.search(r'\bPK\s+WND\s+\d{3}(\d{2,3})/\d{4}\b',raw)
   else:m=re.search(r'\b(?:\d{3}|VRB)\d{2,3}G(\d{2,3})KT\b',raw)
   if not m:raise ValueError((r['station'],r['season_year'],'Q2 raw absent'))
   v=float(m.group(1))
  p['kn']=v;r['qc_correction']='ISD 未核按冻结规则保留 IEM 值；旧脚本漏传值';r['generated_edt']=edt()
 rows.append(r)
assert len(rows)==435 and all(not r.get('valid') or r['qc_peak']['kn'] is not None for r in rows)
with (dst/'qc_station_seasons.jsonl').open('x') as f:
 for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
shutil.copyfile(src/'qc_log.csv',dst/'qc_log.csv')
for name in ('station_admission.csv','static_gates.csv','era_seasons.jsonl'):shutil.copyfile(src/name,dst/name)
(dst/'qc_provenance.json').write_text(json.dumps({'generated_edt':edt(),'rows':435,'null_fixed':sum('qc_correction' in r for r in rows),'parent_invalid':'No-ISD candidates incorrectly assigned null; NaN decision is void','status':'QC frozen before any valid pairing'},ensure_ascii=False,indent=2))
print((dst/'qc_provenance.json').read_text())
