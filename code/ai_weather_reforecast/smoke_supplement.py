"""Smoke-test station diagnostics before the long forecast batch ends."""
from pathlib import Path
s=Path('/content/ai_weather_metrics_supp_v3.py').read_text().split("for e in ('E1','E2','E3'):\n CURRENT_EVENT=e")[0]
exec(compile(s,'supp_prefix.py','exec'))
for e in ('E1','E2','E3'):
 d=file_truth(e,'valid')
 station_rows(d,e,'ERA5',terrain=d['zsfc'])
 station_rows(d,e,'ERA5',full=True,terrain=d['zsfc'])
 print('SMOKE',e,'rows',len(rows),'last',rows[-1],flush=True)
assert len(rows)==54
