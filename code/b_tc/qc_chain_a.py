#!/usr/bin/env python3
"""Post-hoc physical QC sensitivity; never overwrite raw pilot outputs."""
import csv,json,statistics
from collections import defaultdict
from pathlib import Path
p=Path(__file__).resolve().parent
rows=list(csv.DictReader((p/'pilot5/chain_a_station_rows.csv').open()))
results={}
for label, threshold in [('minimum_50pct',720),('strict_90pct',1296)]:
 valid=[];excluded=[]
 for r in rows:
  reason=''
  if not r['ratio_sustained']:reason='no observation or valid model'
  elif int(r['obs_sknt_rows'])<threshold:reason='insufficient temporal completeness'
  elif float(r['obs_peak_5sec_gust_kt'])<float(r['obs_peak_sustained_kt']):reason='gust less than sustained peak: suspect 1min sensor data'
  if reason:excluded.append({'event':r['event'],'station':r['station'],'reason':reason})
  else:valid.append(r)
 vals=[float(r['ratio_sustained'])-1 for r in valid];groups=defaultdict(list)
 for r in valid:groups[r['event']].append(float(r['ratio_sustained'])-1)
 results[label]={'n':len(vals),'median_absolute_ratio_error':statistics.median(abs(x) for x in vals) if vals else None,'median_signed_ratio_bias':statistics.median(vals) if vals else None,'per_event':{k:{'n':len(v),'median_absolute_ratio_error':statistics.median(abs(x) for x in v),'median_signed_ratio_bias':statistics.median(v)} for k,v in sorted(groups.items())},'excluded':excluded}
(p/'chain_a_qc_sensitivity.json').write_text(json.dumps(results,indent=2,ensure_ascii=False))
print(json.dumps({k:{z:v[z] for z in ('n','median_absolute_ratio_error','median_signed_ratio_bias','per_event')} for k,v in results.items()},indent=2))
