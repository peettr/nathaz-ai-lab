"""Compute Case A metrics on downloaded point samples, no solver on 工作站."""
from pathlib import Path
import json,math,statistics,sys
R=Path(__file__).parent
def pearson(x,y):
 a=statistics.mean(x);b=statistics.mean(y);den=math.sqrt(sum((v-a)**2 for v in x)*sum((v-b)**2 for v in y));return sum((v-a)*(w-b) for v,w in zip(x,y))/den if den else None
def metrics(rows,variant):
 a=[p[variant]['speed'] for p in rows];b=[p['obs_speed'] for p in rows];ak=[p[variant]['k'] for p in rows];bk=[p['obs_k'] for p in rows]
 assert all(math.isfinite(v) for v in a+ak+b+bk)
 keep=[i for i,k in enumerate(bk) if abs(k)>.05];ka=[ak[i] for i in keep];kb=[bk[i] for i in keep]
 rmse=math.sqrt(statistics.mean((v-w)**2 for v,w in zip(a,b)))
 return {'n':len(a),'n_tke':len(keep),'FAC2':statistics.mean(.5*w<=v<=2*w for v,w in zip(a,b)), 'q_abs025':statistics.mean(abs(v-w)<=.25 for v,w in zip(a,b)), 'q_rel025':statistics.mean(abs(v-w)<=.25*abs(w) for v,w in zip(a,b)), 'r':pearson(a,b), 'NRMSE_range':rmse/(max(b)-min(b)), 'NRMSE_mean':rmse/statistics.mean(b),'TKE_FAC2':statistics.mean(.5*w<=v<=2*w for v,w in zip(ka,kb)), 'TKE_r':pearson(ka,kb),'mean_ratio':statistics.mean(a)/statistics.mean(b),'mixed_solid':sum(p[variant]['fluid_corners']<8 for p in rows),'below_first_center':sum(p[variant]['below_first_center'] for p in rows)}
out={}
for p in sorted((R/'final/out').glob('samples_*.json')):
 d=json.loads(p.read_text());name=d['name'];out[name]={'dx_m':d['dx_m'],'selected_shift':d['selected_shift'],'group_height_m':d['group_height_m'],'diagnostic_height_m':d['diagnostic_height_m'],'primary':{},'diagnostic':{}}
 for setkey,key in (('primary','groups'),('diagnostic','diagnostic')):
  for group,rows in d[key].items():
   if setkey=='primary':assert len(rows)==(66 if group=='vertical' else 60)
   out[name][setkey][group]={v:metrics(rows,v) for v in ('no_shift','selected')}
(R/'metrics_caseA_r216_0b.json').write_text(json.dumps(out,indent=2,allow_nan=False))
for name,x in out.items():
 print(name,'IoU',x['selected_shift']['iou'],'shift',x['selected_shift']['shift']);
 for group,m in x['primary'].items():print(group, 'selected',m['selected'])
