"""Compare city runs on frozen R10a points and Case E After W observations."""
from pathlib import Path
import json,statistics,csv,math
R=Path(__file__).resolve().parent
H=R.parents[2]/'04_Handoffs/from_22_Lab_20261015/06_Logs_luw'
assert H.exists(),H
D={
 'R10a_no_model':json.loads((H/'run_r10_20261014/offset_samples_a_r10.json').read_text()),
 'lab_first_FP16C':json.loads((H/'wallmodel/cont5_city_samples.json').read_text())}
for tag in ('mix00','mix07','mix10'):
 f=R/(tag+'_samples.json')
 if f.exists():D[tag+'_FP32']=json.loads(f.read_text())
assert all(len(v['rows'])==80 for v in D.values())
ids=[p['id'] for p in D['R10a_no_model']['rows']]
assert len(set(ids))==80 and all([p['id'] for p in d['rows']]==ids for d in D.values())
refs={r['id']:r for r in D['R10a_no_model']['rows']}
out={};per=[]
for name,d in D.items():
 out[name]={'mask_10m':sorted((x for x in d['mask_fit'] if x['z_vtk']==10),key=lambda a:a['iou'] or -1,reverse=True)[:3]}
 for kind in ('sim_ratio','exp_ratio'):
  for group,group_ids in [('all',set(ids)),('wall_50_51_52_54',{50,51,52,54}),('open_23_25_37_17',{23,25,37,17})]:
   rows=[q for q in d['rows'] if q['id'] in group_ids]
   assert len(rows)==len(group_ids)
   y=[q['sample']['plus_dx'][kind] for q in rows];x=[q['after'] for q in rows]
   out[name][kind+'_'+group]={'MAE':statistics.mean(abs(a-b) for a,b in zip(x,y)),'r':statistics.correlation(x,y),'mean_ratio':statistics.mean(y)/statistics.mean(x),'n':len(rows)}
 out[name]['upstream']={str(v['x_local_m']):v['fraction_input'] for v in d['upstream'] if v['z_m']==2. and v['x_local_m'] in (25.,42.)}
 for q in d['rows']:
  ref=refs[q['id']]
  a=q['sample']['plus_dx']['exp_ratio'];b=ref['sample']['plus_dx']['exp_ratio']
  per.append({'run':name,'id':q['id'],'obs_after':q['after'],'S':q['sample']['plus_dx']['sim_ratio'],'Sstar':a,'baseline_Sstar':b,'delta_Sstar':a-b,'delta_abs_err_Sstar':abs(a-q['after'])-abs(b-q['after']),'fluid_corners':q['sample']['plus_dx']['fluid_corners']})
 if name!='R10a_no_model':
  group=[q for q in per if q['run']==name]
  out[name]['direction']={'Sstar_up':sum(q['delta_Sstar']>0 for q in group),'Sstar_down':sum(q['delta_Sstar']<0 for q in group),'MAE_improved':sum(q['delta_abs_err_Sstar']<0 for q in group),'MAE_worse':sum(q['delta_abs_err_Sstar']>0 for q in group),'unchanged':sum(q['delta_abs_err_Sstar']==0 for q in group)}
(R/'city_metrics.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
with (R/'point_changes.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(per[0]));w.writeheader();w.writerows(per)
print(json.dumps(out,indent=2))
