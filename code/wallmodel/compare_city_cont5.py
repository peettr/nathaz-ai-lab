"""Compare Case E R10a and diagnostic wall model on identical 80 points."""
from pathlib import Path
import json,math,statistics
r=Path(__file__).resolve().parent;root=r.parent
old=json.loads((root/'run_r10_20261014/offset_samples_a_r10.json').read_text());new=json.loads((r/'cont5_city_samples.json').read_text())
assert len(old['rows'])==len(new['rows'])==80
assert [p['id'] for p in old['rows']]==[p['id'] for p in new['rows']]
res={'note':'internal diagnostic, empty-field gate relaxed by Lead; 15.9m inflow normalization, After W','mask_best':{},'metrics':{},'point_changes':[]}
for z in sorted(set(a['z_vtk'] for a in new['mask_fit'])):
 fit=sorted((a for a in new['mask_fit'] if a['z_vtk']==z),key=lambda a:a['iou'] or -1,reverse=True);res['mask_best'][str(z)]=fit[:4]
for name,data in [('R10a',old),('wall_first',new)]:
 res['metrics'][name]={}
 for label,ids in [('all',None),('wall50_51_52_54',{50,51,52,54}),('street_open',{4,39,44,75})]:
  rows=[p for p in data['rows'] if ids is None or p['id'] in ids]
  res['metrics'][name][label]={}
  for kind in ('sim_ratio','exp_ratio'):
   x=[p['after'] for p in rows];y=[p['sample']['plus_dx'][kind] for p in rows]
   res['metrics'][name][label][kind]=dict(n=len(x),MAE=statistics.mean(abs(a-b) for a,b in zip(x,y)),r=statistics.correlation(x,y) if len(x)>2 else None,mean_ratio=statistics.mean(y)/statistics.mean(x),sim_mean=statistics.mean(y))
for a,b in zip(old['rows'],new['rows']):
 res['point_changes'].append(dict(id=a['id'],after=a['after'],before=a['sample']['plus_dx']['exp_ratio'],wall=b['sample']['plus_dx']['exp_ratio'],delta=b['sample']['plus_dx']['exp_ratio']-a['sample']['plus_dx']['exp_ratio'],old_fluid=a['sample']['plus_dx']['fluid_corners'],new_fluid=b['sample']['plus_dx']['fluid_corners']))
res['upstream']={'R10a':old['upstream'],'wall_first':new['upstream']}
(r/'metrics_city_cont5.json').write_text(json.dumps(res,ensure_ascii=False,indent=2))
print('mask',res['mask_best']);print('metrics',res['metrics'])
