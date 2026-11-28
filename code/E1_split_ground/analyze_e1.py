"""Recompute E1 vs frozen B2/Gz2 from the three original 80-point files."""
from pathlib import Path
import json,csv,statistics,math
R=Path(__file__).resolve().parent
P=R.parents[1]/'wp1_nearwall/city_z0'
B=json.loads((R.parents[1]/'wp1b_ibm/inflow_ti/B2_offset_samples.json').read_text())
G=json.loads((P/'Gz2_offset_samples_a_r10.json').read_text())
E=json.loads((R/'E1_offset_samples.json').read_text())
rows={v:{r['id']:r for r in obj['rows']} for v,obj in [('B2',B),('Gz2',G),('E1',E)]}
assert all(set(t)==set(range(1,81)) for t in rows.values())
for i in range(1,81):
 assert all(abs(rows[a][i]['after']-rows['B2'][i]['after'])<1e-10 for a in ('Gz2','E1'))
assert all(abs(obj['uref']-B['uref'])<1e-6 for obj in (G,E))
fast={7,8,17,20,23,25,26,27,45,68};slow={i for i,r in rows['B2'].items() if r['sample']['plus_dx']['sim_ratio']/r['after']<.8}
front={i for i,r in rows['B2'].items() if r['xls_xy'][0]+250<165 and i!=23}
deep={i for i,r in rows['B2'].items() if r['xls_xy'][0]+250>=200}
groups={'all80':set(range(1,81)),'front_xlt165_ex23':front,'deep_xge200':deep,'fast10':fast,'slow41':slow,'wall4':{50,51,52,54},'open4':{23,25,37,17}}
def calc(case,ids,kind):
 obs=[rows[case][i]['after'] for i in sorted(ids)]
 pred=[rows[case][i]['sample']['plus_dx'][kind] for i in sorted(ids)]
 return {'n':len(ids),'MAE':statistics.mean(abs(a-b) for a,b in zip(pred,obs)),'r':statistics.correlation(pred,obs) if len(ids)>1 else None,'mean_ratio':statistics.mean(pred)/statistics.mean(obs)}
metrics={'groups':{g:{case:{kind:calc(case,ids,kind) for kind in ('sim_ratio','exp_ratio')} for case in rows} for g,ids in groups.items()},'groups_ids':{k:sorted(v) for k,v in groups.items()}}
for target in ('B2','Gz2'):
 change=[]
 for i in range(1,81):
  w=rows['E1'][i]['after'];a=rows['E1'][i]['sample']['plus_dx']['exp_ratio'];b=rows[target][i]['sample']['plus_dx']['exp_ratio']
  change.append({'id':i,'W':w,'E1':a,target:b,'improve':abs(a-w)<abs(b-w),'worse':abs(a-w)>abs(b-w)})
 metrics['E1_vs_'+target]={'improve':sum(q['improve'] for q in change),'worse':sum(q['worse'] for q in change),'same':sum(not q['improve'] and not q['worse'] for q in change)}
 with (R/('points_vs_'+target+'.csv')).open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(change[0]));writer.writeheader();writer.writerows(change)
metrics['upwind']={case:{str(x):next((r['fraction_input'] for r in obj['upstream'] if r['z_m']==2. and r['x_local_m']==x),None) for x in (25.,42.)} for case,obj in [('B2',B),('Gz2',G),('E1',E)]}
metrics['upwind_officialU2']={case:{x:(v*2.964/B['uref'] if v is not None else None) for x,v in vals.items()} for case,vals in metrics['upwind'].items()}
(R/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(metrics,ensure_ascii=False,indent=2))
