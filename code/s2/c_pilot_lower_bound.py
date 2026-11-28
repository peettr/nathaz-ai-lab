#!/usr/bin/env python3
import csv,json
from pathlib import Path
p=Path(__file__).resolve().parent
v=list(csv.DictReader((p.parent/'v1/run2/station_rows_v1.csv').open()))
c={x['station']:x for x in csv.DictReader((p/'c_pang_milton48_stations.csv').open())}
out=[]
for x in v:
 if x['event']!='MILTON' or x['reason']!='truncated':continue
 for var in ('s','g'):
  obs=float(x['obs_'+var+'_kt'] or 0)
  pred=float(c[x['station']]['pred_'+var+'_kt'])
  out.append(dict(event='MILTON',station=x['station'],chain='c_PANG_pilot',lead_h=48,variable=var,observed_lower_bound_kt=obs or '',predicted_kt=pred,below=(pred<obs if obs else ''),status='evaluable' if obs else 'no_observed_lower_bound'))
with (p/'censored_lower_bound_c_pilot.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,out[0].keys());w.writeheader();w.writerows(out)
lines=['# (c) Milton 48 h 单事件截尾站下限（不代表全样本）','']
for var in ('s','g'):
 rr=[x for x in out if x['variable']==var and x['status']=='evaluable']
 below=[x for x in rr if x['below']]
 lines.append(f'{var}: {len(below)}/{len(rr)} 模型峰低于已观测下限；站点 '+', '.join(x['station'] for x in below))
lines.append('逐站见 censored_lower_bound_c_pilot.csv；其它事件和提前量未计算，不能合并到完整 (c) 链。')
(p/'censored_lower_bound_c_pilot.md').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
