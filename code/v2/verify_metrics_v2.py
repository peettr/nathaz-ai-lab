"""Independent readback of v2 hit/false-alarm denominators and immutable verified metrics."""
from pathlib import Path
import json,csv,math
r=Path('./22_Lab/06_Logs/e_terrain/v2')
m=json.loads((r/'metrics_v2.json').read_text());rows=[x for x in csv.DictReader((r/'paired_main_v2_raw.csv').open()) if x['period']=='test']
for method,col in [('bilinear','bilinear_ms'),('windninja','wn_ms'),('mos','mos_ms'),('windninja_mos','wn_mos_ms')]:
 av=[x for x in rows if x[col] not in ('','nan','NaN')]
 yes=[x for x in av if float(x['obs_ms'])>=float(x['p99'])];no=[x for x in av if float(x['obs_ms'])<float(x['p99'])]
 hit=sum(float(x[col])>=float(x['p99']) for x in yes);false=sum(float(x[col])>=float(x['p99']) for x in no)
 m['all'][method].update({'p99_hit_rate':hit/len(yes) if yes else None,'p99_false_alarm_rate':false/len(no) if no else None,'p99_event_n':len(yes),'p99_nonevent_n':len(no),'p99_hit_count':hit,'p99_false_count':false})
 assert len(av)==m['test_n']-(m['windninja_mos_missing_test_n'] if method=='windninja_mos' else 0)
m['verification']='Independent stdlib CSV readback, exclude unavailable forecast from event/non-event denominator; raw numerical run preserved as metrics_v2_raw.json.'
(r/'metrics_v2_verified.json').write_text(json.dumps(m,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print('VERIFIED',m['pass'],[(k,v['p99_false_alarm_rate'],v['p99_nonevent_n']) for k,v in m['all'].items()])
