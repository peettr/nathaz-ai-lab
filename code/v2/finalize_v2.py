"""Resolve gate on full strong cohort; preserve raw analysis and explicitly audit missing MOS."""
import csv,json,math
from pathlib import Path
r=Path('./22_Lab/06_Logs/e_terrain/v2')
m=json.loads((r/'metrics_v2_raw.json').read_text());rows=list(csv.DictReader((r/'paired_main_v2_raw.csv').open()))
test=[x for x in rows if x['period']=='test'];strong=[x for x in test if float(x['obs_ms'])>=float(x['p90'])]
assert len(test)==m['test_n'] and len(strong)==m['strong_n']
missing=[x for x in test if x['wn_mos_ms'] in ('','nan','NaN')]
missing_strong=[x for x in strong if x['wn_mos_ms'] in ('','nan','NaN')]
assert m['main_windninja_success_n']==m['main_expected_n'] and not m['failures']
assert len(missing_strong)==0,(len(missing_strong),'cannot evaluate full strong MOS gate')
assert all(math.isfinite(float(x['wn_ms'])) for x in test)
b=m['strong']['bilinear']['mae_ms'];w=m['strong']['windninja']['mae_ms'];assert math.isfinite(b) and math.isfinite(w)
m['strong_reduction_pct']=100*(1-w/b)
m['windninja_mos_missing_test_n']=len(missing)
m['windninja_mos_missing_strong_n']=len(missing_strong)
m['windninja_mos_unavailable']=[{'station':x['station'],'valid_utc':x['valid_utc'],'sector':x['wn_sector']} for x in missing]
m['all_time_windninja_mos_scored_n']=len(test)-len(missing)
m['pass']=bool(all(m['gates'].values()))
m['audit']='All 207 main strong cases have four paired method scores. One non-strong test case lacks a training WindNinja output-direction sector and is omitted only from the report-only full-time WN+MOS score; (a), (b), (c) have complete predeclared denominators.'
(r/'metrics_v2.json').write_text(json.dumps(m,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print('FINALIZED',m['pass'],m['strong_n'],m['strong_reduction_pct'],m['station_wins'],len(missing))
