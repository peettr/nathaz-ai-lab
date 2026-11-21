"""Remove common same-height no-model bias, diagnostic only."""
import json,csv
from pathlib import Path
R=Path(__file__).resolve().parent
N=json.loads((R.parent/'A_impl/none_profile.json').read_text())
V={t:json.loads((R.parent/'stress_budget'/f'{t}_profile.json').read_text()) for t in ('mixing07','mixing')}
lookup=lambda d:{(p['x'],p['z']):p['ratio'] for p in d['rows']}
n=lookup(N)
with (R/'empty_bias_subtracted.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['variant','x_m','z_m','none_U_over_Uin','variant_U_over_Uin','variant_minus_none','residual_from_one_pct'])
 for t,d in V.items():
  v=lookup(d)
  for x in (200,300,400):
   for z in range(2,21):
    a=v[x,z];b=n[x,z];w.writerow([t,x,z,b,a,a-b,100*(a-b)])
    if z in (2,5,10,20):print(t,x,z,round((a-b)*100,3))
