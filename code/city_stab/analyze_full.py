"""Analyze frozen 80-point Case E observations; run on small JSON only."""
from pathlib import Path
import json,statistics,csv
R=Path(__file__).resolve().parent
H=R.parents[2]/'04_Handoffs/from_22_Lab_20261015/06_Logs_luw'
D={'old_nomodel_FP16C':json.loads((H/'run_r10_20261014/offset_samples_a_r10.json').read_text()),'old_first_FP16C':json.loads((H/'wallmodel/cont5_city_samples.json').read_text())}
for tag in ('a0','a07','a10'):
    f=R/(tag+'_samples.json')
    if f.exists(): D[tag+'_FP32']=json.loads(f.read_text())
assert all(len(d['rows'])==80 for d in D.values())
ids=[p['id'] for p in D['old_nomodel_FP16C']['rows']]
assert len(set(ids))==80 and all([p['id'] for p in d['rows']]==ids for d in D.values())
base={r['id']:r for r in D['old_nomodel_FP16C']['rows']}
out={};per=[]
for name,d in D.items():
    out[name]={}
    for key in ('sim_ratio','exp_ratio'):
        for group,subset in [('all',set(ids)),('wall_50_51_52_54',{50,51,52,54}),('open_23_25_37_17',{23,25,37,17})]:
            rows=[q for q in d['rows'] if q['id'] in subset];assert len(rows)==len(subset)
            obs=[q['after'] for q in rows];sim=[q['sample']['plus_dx'][key] for q in rows]
            out[name][key+'_'+group]={'MAE':statistics.mean(abs(a-b) for a,b in zip(obs,sim)),'r':statistics.correlation(obs,sim),'mean_ratio':statistics.mean(sim)/statistics.mean(obs)}
    out[name]['upstream']={str(v['x_local_m']):v['fraction_input'] for v in d['upstream'] if v['z_m']==2. and v['x_local_m'] in (25.,42.)}
    out[name]['mask_10m']=sorted((x for x in d['mask_fit'] if x['z_vtk']==10),key=lambda a:a['iou'] or -1,reverse=True)[:1]
    for q in d['rows']:
        a=q['sample']['plus_dx']['exp_ratio'];b=base[q['id']]['sample']['plus_dx']['exp_ratio'];obs=q['after']
        per.append({'run':name,'id':q['id'],'obs_after':obs,'S':q['sample']['plus_dx']['sim_ratio'],'Sstar':a,'baseline_Sstar':b,'delta_Sstar':a-b,'delta_abs_err_Sstar':abs(a-obs)-abs(b-obs),'fluid_corners':q['sample']['plus_dx']['fluid_corners']})
    if name!='old_nomodel_FP16C':
        group=[q for q in per if q['run']==name]
        out[name]['direction']={'Sstar_up':sum(q['delta_Sstar']>0 for q in group),'Sstar_down':sum(q['delta_Sstar']<0 for q in group),'MAE_improved':sum(q['delta_abs_err_Sstar']<0 for q in group),'MAE_worse':sum(q['delta_abs_err_Sstar']>0 for q in group),'unchanged':sum(q['delta_abs_err_Sstar']==0 for q in group)}
(R/'city_full_metrics.json').write_text(json.dumps(out,indent=2))
with (R/'city_full_point_changes.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(per[0]));w.writeheader();w.writerows(per)
print(json.dumps(out,indent=2))
