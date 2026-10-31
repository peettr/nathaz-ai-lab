"""Reduce only archived E1/E05 and new E1G0A35/A70 outputs."""
from pathlib import Path
import csv,json,statistics,math
R=Path(__file__).resolve().parent
base=R.parent.parent/'wp1b_ibm/resolution_split/profiles_five_stations.csv'
rows=[]
for r in csv.DictReader(base.open()):
 if r['tag'] in ('E1','E05') and r['availability']=='measured':rows.append({k:float(r[k]) if k!='tag' else r[k] for k in ('tag','x_m','z_m','U_mps','k_m2s2')})
for t in ('E1G0','E1G0A35','E1G0A70'):
 p=(R.parent/'approach_keep/E1G0_offset_samples_a_r10.json' if t=='E1G0' else R/(t+'_samples.json'))
 d=json.loads(p.read_text())
 for q in d['profiles']: rows.append(dict(tag=t,x_m=float(q['x']),z_m=float(q['z_agl']),U_mps=float(q['U_mps']),k_m2s2=float(q['k_m2s2'])))
with (R/'profiles_approach_keep2.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=('tag','x_m','z_m','U_mps','k_m2s2'));w.writeheader();w.writerows(rows)
b={(r['tag'],r['x_m'],r['z_m']):r for r in rows}
out={}
def upstream_159(t):
 p=(R.parent.parent/'wp1b_ibm/resolution_split'/f'{t}_samples.json' if t in ('E1','E05') else R.parent/'approach_keep/E1G0_offset_samples_a_r10.json' if t=='E1G0' else R/(t+'_samples.json'))
 d=json.loads(p.read_text())
 a={float(q['x_local_m']):float(q['mean_speed_mps']) for q in d['upstream'] if abs(float(q['z_m'])-15.9)<1e-5}
 return a
for t in ('E1','E05','E1G0','E1G0A35','E1G0A70'):
 v={}
 for z in (2.,5.,10.,15.9):
  if z==15.9:
   u5=upstream_159(t)[5.];u42=upstream_159(t)[42.];ref=upstream_159('E05')[42.]
  else:
   u5=b[t,5.,z]['U_mps'];u42=b[t,42.,z]['U_mps'];ref=b['E05',42.,z]['U_mps']
  v[str(z)]=dict(U5=u5,U42=u42,retention=u42/u5,vs_E05_pct=100*(u42/ref-1),k42=b[t,42.,z]['k_m2s2'] if z!=15.9 else None)
 if t.startswith('E1G0'):
  p=R.parent/'approach_keep/E1G0_wall_tau_actual.csv' if t=='E1G0' else R/(t+'_wall_tau_actual.csv')
  by={x:[] for x in (5,15,25,35,42)}
  for q in csv.DictReader(p.open()):
   x=int(q['x']);y=int(q['y'])
   if x in by and y in range(100,311,30):by[x].append(float(q['ustar_mps']))
  v['ustar_mps']={x:statistics.mean(a) if a else None for x,a in by.items()}
 out[t]=v
(R/'summary.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(out,indent=2,ensure_ascii=False))
