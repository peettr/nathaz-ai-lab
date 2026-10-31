"""Colab CPU overlap-only summaries for station-stage preregistration."""
import csv,json,collections,statistics
from pathlib import Path
p=Path('/content')
seasons=list(csv.DictReader((p/'season_metrics.csv').open()))
peaks=list(csv.DictReader((p/'peak_events.csv').open()))
assert len(seasons)==360 and len(peaks)==1074
out={}
for st in sorted({r['station'] for r in seasons}):
 v=[r for r in seasons if r['station']==st and 2000<=int(r['season'][:4])<=2009]
 w=[r for r in peaks if r['station']==st and 2000<=int(r['season'][:4])<=2009]
 minute=[r for r in w if r['peak_type']=='minute']
 combined=[]
 for r in v:
  cand=[x for x in w if x['season']==r['season'] and x['peak_type']==('metar_pk' if r['metar_peak_source']=='pk' else 'metar_gust')]
  if cand:combined.append(cand[0])
 out[st]={'seasons':len(v),'minute_available':len(minute),'wind_coverage_median_pct':round(statistics.median(float(x['wind_coverage'])*100 for x in v),2),'wind_below_90':sum(float(x['wind_coverage'])<.9 for x in v),'minute_raw_discordance20':sum(x['qc_discordance20kn']=='True' for x in v),'minute_raw_isolated':sum(x['qc_isolated30kn_jump']=='True' for x in v),'metar_combined_labels':dict(collections.Counter(x['mechanism'] for x in combined)),'minute_labels':dict(collections.Counter(x['mechanism'] for x in minute)),'minute_missing_seasons':[x['season'] for x in v if not x['minute_peak_knots']]}
(p/'overlap_summary.json').open('x').write(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False))
