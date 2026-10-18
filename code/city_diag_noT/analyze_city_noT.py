"""Analyze Case E no-temperature variants against same-run FP32 baseline."""
from pathlib import Path
import json,csv,statistics
R=Path(__file__).resolve().parent
B=json.loads((R.parent/'city_stab/stage6noT_offset_samples_a_r10.json').read_text())
ref={x['id']:x for x in B['rows']};assert len(ref)==80
out={};rows=[]
for tag in ('G0','G1','G2'):
 p=R/(tag+'_offset_samples_a_r10.json')
 if not p.exists():continue
 d=json.loads(p.read_text());q={x['id']:x for x in d['rows']};assert set(q)==set(ref)
 out[tag]={}
 for group,ids in [('all',set(ref)),('wall',{50,51,52,54}),('open',{23,25,37,17})]:
  out[tag][group]={}
  for kind in ('sim_ratio','exp_ratio'):
   s=[q[i]['sample']['plus_dx'][kind] for i in sorted(ids)]
   y=[q[i]['after'] for i in sorted(ids)]
   out[tag][group][kind]={'MAE':statistics.mean(abs(x-z) for x,z in zip(s,y)), 'r':statistics.correlation(s,y), 'mean_ratio':statistics.mean(s)/statistics.mean(y)}
 out[tag]['upstream']={str(x['x_local_m']):x['fraction_input'] for x in d['upstream'] if x['z_m']==2.0 and x['x_local_m'] in (25.,42.)}
 change=[]
 for i in sorted(ref):
  x=q[i]['sample']['plus_dx']['exp_ratio'];b=ref[i]['sample']['plus_dx']['exp_ratio'];y=q[i]['after']
  v={'run':tag,'id':i,'obs':y,'S':q[i]['sample']['plus_dx']['sim_ratio'],'Sstar':x,'baseline_Sstar':b,'delta_Sstar':x-b,'delta_abs_error':abs(x-y)-abs(b-y)};rows.append(v);change.append(v)
 out[tag]['change_counts']={k:sum(bool(fn(v)) for v in change) for k,fn in {'up':lambda v:v['delta_Sstar']>0,'down':lambda v:v['delta_Sstar']<0,'equal':lambda v:v['delta_Sstar']==0,'improved':lambda v:v['delta_abs_error']<0,'worse':lambda v:v['delta_abs_error']>0,'same_error':lambda v:v['delta_abs_error']==0}.items()}
 trace=R/(tag+'_trace.csv')
 if trace.exists():
  a=list(csv.DictReader(trace.open()));valid=[v for v in a if not v['first_nonfinite_xyz_component']];out[tag]['trace']={'rows':len(a),'last_step':int(a[-1]['step']),'nonfinite':len(valid)!=len(a),'max_u':max(float(v['max_u_lattice']) for v in valid),'rho_after3000':[min(float(v['min_rho']) for v in valid if int(v['step'])>=3000),max(float(v['max_rho']) for v in valid if int(v['step'])>=3000)]}
(R/'metrics.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
if rows:
 with (R/'point_changes.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(out,indent=2,ensure_ascii=False))
