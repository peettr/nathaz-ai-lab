#!/usr/bin/env python3
"""Create immutable screened A2 view: Case III yaw quality gate failed."""
import json
from pathlib import Path
h=Path(__file__).resolve().parent
src=h/'metrics_A2.json';out=h/'metrics_A2_screened.json'
if out.exists():raise RuntimeError('refuse overwrite')
j=json.loads(src.read_text())
raw_runs=j.pop('runs');raw_ratios=j.pop('benefit_ratios')
j['screening']='Case III: yaw actuator enabled and moves, but wind reaches 111 deg while nacelle is ~33 deg; 1s yaw change can exceed 0.3 deg. Per A2 task, no Case III load or benefit values released. Raw simulations remain in WSL; metrics_A2.json is unscreened diagnostic only.'
j['runs']=[r if r['case']=='I_near' else {k:v for k,v in r.items() if k not in ('metrics','runroot')}|{'status':'yaw_invalid_no_load_released'} for r in raw_runs]
j['benefit_ratios']=[r for r in raw_ratios if r['case']=='I_near']
j['yaw_diagnostic_III']={'run_count':sum(r['case']=='III_offset' for r in raw_runs),'wind_max_deg':111.1451519230966,'nac_yaw_at_wind_max_deg':33.02,'heading_lag_at_wind_max_deg':78.12515192309661,'nac_yaw_peak_deg':41.66,'feedback_max_1s_change_deg':next(r['yaw_max_1s_change_deg'] for r in raw_runs if (r['case'],r['group'])==('III_offset','feedback'))}
out.write_text(json.dumps(j,indent=2,ensure_ascii=False)+'\n')
print(out,'released cases',len([r for r in j['runs'] if 'metrics' in r]),'screened',j['yaw_diagnostic_III']['run_count'])
