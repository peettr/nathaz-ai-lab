#!/usr/bin/env python3.10
"""Read-only T15 noise-floor comparison; do not fill absent upper fields."""
import csv, hashlib, json, math, statistics
from pathlib import Path
import numpy as np
O=Path(__file__).resolve().parent
L=O.parents[1]
T3=L/'R21.4a_T3_emptyground/T3d'
T4=L/'R21.4a_T4_groundWM/phaseB_v2'
T15=L/'R21.4a_T15_second_layer_WM/emptyfield_v2b_20261119_0211'
P15=T15/'postprocess_v2b_fix1'
EV15=next(x for x in T15.glob('session_luw-t15-a100-*/evidence') if (x/'run.done').exists())
inputs={}
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def record(p):
 assert p.is_file(),p
 inputs[str(p)]=digest(p)
 side=Path(str(p)+'.sha256')
 if side.is_file():assert inputs[str(p)]==side.read_text().split()[0],p
 return p
def data(p):return json.loads(record(p).read_text())
profile=record(T4/'stage/dx1p0_s107/wind_bc/profile.dat')
pts=[tuple(map(float,x.split())) for x in profile.read_text().splitlines()[1:]]
a=max((z,u) for z,u in pts if z<=1.5);b=min((z,u) for z,u in pts if z>=1.5)
u15=a[1]+(b[1]-a[1])*(1.5-a[0])/(b[0]-a[0]);design=.4*u15/math.log((1.5+.024)/.024)
rows=[];profiles=[];g3=[]
for seed in (107,108,109):
 for typ,base,label in [('bounce',T3,f'dx1p0_s{seed}'),('T4_first',T4,f'B_dx1p0_s{seed}'),('T15_second',EV15,f'WM_s{seed}')]:
  metric=data((base/(label+'_metrics_wall_corrected.json')) if typ!='T15_second' else (P15/(label+'_metrics.json')))
  if typ=='T15_second':
   prof=list(csv.DictReader(record(P15/(label+'_profile.csv')).open()))
   vals={float(x['z_agl_m']):(float(x['G_x5_mps']),float(x['G_xc_mps'])) for x in prof}
   assert len(vals)==51
   H=metric['H']
  else:
   npz=record((base/(label+'_thin.npz')) if typ=='bounce' else (base/'evidence'/(label+'_thin.npz')))
   with np.load(npz,allow_pickle=False) as d:
    u=d['u_avg'];fluid=d['fluid'];m=json.loads(str(d['metadata']))
    assert u.shape==(28,100,550,3) and fluid.shape==(28,100,550) and m['k_start']==20
    vals={}
    for h2 in np.arange(5.,26.0001,.5):
     k=int(math.floor(20.5+h2));alpha=20.5+h2-k
     speeds=[]
     for x in (5,round(252.1485175)):
      ys=np.arange(40,61);j=k-20
      assert (fluid[j,ys,x]>.5).all() and (fluid[j+1,ys,x]>.5).all()
      vec=(1-alpha)*u[j,ys,x].astype('f8')+alpha*u[j+1,ys,x].astype('f8')
      speeds.append(float(np.linalg.norm(vec,axis=1).mean()))
     vals[float(h2)]=tuple(speeds)
   H=metric['xc_G2_mps']/metric['inlet_G2_at_x5_mps']
  for h,(g5,gc) in vals.items(): profiles.append({'seed':seed,'configuration':typ,'z_agl_m':h,'G_x5_mps':g5,'G_xc_mps':gc,'signed_deviation':gc/g5-1})
  taupath=(T4/'evidence'/(label+'_wall_tau_actual.csv')) if typ=='T4_first' else EV15/(label+'_wall_tau_actual.csv')
  tm=ti=None
  if typ!='bounce':
   tau=list(csv.DictReader(record(taupath).open()))
   def us(x):
    rr=[float(v['ustar_mps']) for v in tau if int(v['x'])==x and 2<=int(v['y'])<=97]
    assert len(rr)>=90
    return statistics.mean(rr),len(rr)
   tm,nmid=us(275);ti,nin=us(5)
  else:nmid=nin=None
  subset={h:vals[h][1]/vals[h][0]-1 for h in vals}
  def avg(lo,hi):
   rr=[v for h,v in subset.items() if lo<=h<=hi];return statistics.mean(rr) if rr else None
  def ma(lo,hi):
   rr=[abs(v) for h,v in subset.items() if lo<=h<=hi];return max(rr) if rr else None
  rows.append({'seed':seed,'configuration':typ,'H_G1':H,'G2_5to30_max_abs':ma(5,30) if len(vals)==51 else None,'G2_5to26_max_abs_common':ma(5,26),'deviation_15to30_mean':avg(15,30) if len(vals)==51 else None,'deviation_15to26_mean_common':avg(15,26),'available_profile_height_max_m':max(vals),'G3_eligible_fetch_mid_ustar_ratio':tm/design if tm is not None else None,'x5_eligible_ustar_ratio':ti/design if ti is not None else None,'ustar_fetch_mid_mps':tm,'ustar_x5_mps':ti,'eligible_columns_fetch_mid':nmid,'eligible_columns_x5':nin})
  g3.append((seed,typ,tm/design if tm is not None else None,ti/design if ti is not None else None))
# Independent artifact provenance for T15 2m and full upper-profile data.
for seed in (107,108,109):record(EV15/f'WM_s{seed}_profile_upper.npz')
record(T4/'B_verdict.json');record(P15/'T15_verdict.json')
summary={}
for key in ('deviation_15to26_mean_common','G2_5to26_max_abs_common','G3_eligible_fetch_mid_ustar_ratio','x5_eligible_ustar_ratio'):
 summary[key]={}
 for typ in ('bounce','T4_first','T15_second'):
  vv=[r[key] for r in rows if r['configuration']==typ]
  summary[key][typ]={'by_seed':vv,'range':max(vv)-min(vv) if all(x is not None for x in vv) else None}
for typ in ('T4_first','T15_second'):
 summary['paired_15to26_'+typ+'_minus_bounce']=[next(r['deviation_15to26_mean_common'] for r in rows if r['seed']==s and r['configuration']==typ)-next(r['deviation_15to26_mean_common'] for r in rows if r['seed']==s and r['configuration']=='bounce') for s in (107,108,109)]
def pearson(a,b):
 av=statistics.mean(a);bv=statistics.mean(b);den=math.sqrt(sum((x-av)**2 for x in a)*sum((x-bv)**2 for x in b));return sum((x-av)*(y-bv) for x,y in zip(a,b))/den if den else None
summary['paired_seed_pearson_15to26_mean']={typ:pearson(summary['deviation_15to26_mean_common']['bounce']['by_seed'],summary['deviation_15to26_mean_common'][typ]['by_seed']) for typ in ('T4_first','T15_second')}
out={'definition':{'G2':'G=mean_y40:60 |interpolated mean velocity vector|; xc=252.1485175 rounded to x252, x5=5; 0.5 m heights 5..26 common, 5..30 only T15','G3':'mean of eligible column ustar at x275 or x5, y2..97, divided by inlet design ustar from frozen profile at z1.5, kappa .4,z0 .024','missing':'T3d and T4 thin exports stop at k47: no 26.5..30 m interpolation support; T3d bounce has no wall-stress ustar exporter; no substitution'},'rows':rows,'summary':summary,'input_sha256':inputs}
with (O/'NOISEFLOOR_RESULT.json').open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
with (O/'PROFILE_DEVIATIONS.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(profiles[0]));w.writeheader();w.writerows(profiles)
print(json.dumps({'rows':rows,'summary':summary,'file_count':len(inputs)},ensure_ascii=False,indent=2))
