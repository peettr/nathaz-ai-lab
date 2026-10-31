from pathlib import Path
import csv,json,statistics as st
R=Path(__file__).resolve().parent
B=Path('./24_Urban_Wind_LBM/06_Logs/wp1b_ibm/inflow_ti/B2_offset_samples.json')
a=json.loads(B.read_text());b=json.loads((R/'S1_offset_samples.json').read_text());assert len(a['rows'])==len(b['rows'])==80
A={r['id']:r for r in a['rows']};C={r['id']:r for r in b['rows']};assert A.keys()==C.keys()==set(range(1,81))
fast={7,8,17,20,23,25,26,27,45,68};slow={i for i in range(1,81) if A[i]['sample']['plus_dx']['sim_ratio']/A[i]['after']<.8};assert len(slow)==41
# Match E1_split_ground/analyze_e1.py grouping, x_local=xls_x+250.
front={i for i in range(1,81) if i!=23 and A[i]['xls_xy'][0]+250<165}
deep={i for i in range(1,81) if A[i]['xls_xy'][0]+250>=200}
groups={'all':set(A),'front':front,'deep':deep,'fast10':fast,'slow41':slow,'wall4':{50,51,52,54}}
out={'groups':{},'pointwise':[]}
for i in sorted(A):
 p=A[i];q=C[i];assert abs(p['after']-q['after'])<1e-8
 rec={'id':i,'x_local':p.get('x_local_m',p['xls_xy'][0]+250.50008),'y_local':p['xls_xy'][1]+250.60004,'obs':p['after']}
 for tag,row in [('B2',p),('S1',q)]:
  for var in ('sim_ratio','exp_ratio'):rec[f'{tag}_{var}']=row['sample']['plus_dx'][var]
 out['pointwise'].append(rec)
for name,ids in groups.items():
 rows=[out['pointwise'][i-1] for i in sorted(ids)];v={'n':len(rows)}
 for tag in ('B2','S1'):
  v[tag]={}
  for var in ('sim_ratio','exp_ratio'):
   ob=[r['obs'] for r in rows];si=[r[f'{tag}_{var}'] for r in rows]
   v[tag][var]={'mae':st.mean(abs(x-y) for x,y in zip(si,ob)),'r':st.correlation(si,ob) if len(rows)>2 else None,'mean_ratio':st.mean(si)/st.mean(ob)}
  ob=[r['obs'] for r in rows];si=[r[f'{tag}_sim_ratio'] for r in rows];v[tag]['pointwise_error']={'over_pred':sum(x>y for x,y in zip(si,ob)),'under_pred':sum(x<y for x,y in zip(si,ob))}
 v['compare']={}
 for var in ('sim_ratio','exp_ratio'):
  delta=[abs(r[f'S1_{var}']-r['obs'])-abs(r[f'B2_{var}']-r['obs']) for r in rows]
  shift=[r[f'S1_{var}']-r[f'B2_{var}'] for r in rows]
  v['compare'][var]={'improved':sum(d<-1e-9 for d in delta),'worsened':sum(d>1e-9 for d in delta),'tied':sum(abs(d)<=1e-9 for d in delta),'mean_S1_minus_B2':st.mean(shift)}
 out['groups'][name]=v
(R/'metrics.json').write_text(json.dumps(out,indent=2)+'\n')
with (R/'pointwise.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=out['pointwise'][0]);w.writeheader();w.writerows(out['pointwise'])
print(json.dumps(out['groups'],indent=2))
