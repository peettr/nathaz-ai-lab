"""Read-only Case E definition audit; writes only this task's audit JSON."""
import json
from pathlib import Path
import statistics
import xlrd
R=Path(__file__).resolve().parent
ROOT=R.parents[0].parent  # 06_Logs
XLS=Path('./22_Lab/06_Logs/argon_blind_luw/repo/examples/example_ProfileResearch_noDEM/CaseE(Niigata).xls')
W=xlrd.open_workbook(str(XLS)); inflow=W.sheet_by_name('Inflow'); after=W.sheet_by_name('Results (After Construction)')
profile=ROOT/'wp1b_ibm/inflow_ti/stage_B/case/wind_bc/profile.dat'
rows=[]
for line in profile.read_text().splitlines()[1:]:
 z,u=line.split();rows.append((float(z),float(u)))
def interp(points,z):
 for a,b in zip(points,points[1:]):
  if a[0]<=z<=b[0]:return a[1]+(b[1]-a[1])*(z-a[0])/(b[0]-a[0])
 raise ValueError(z)
official=[(float(inflow.cell_value(i,1))*250,float(inflow.cell_value(i,2))*7.8) for i in range(2,14)]
sources={
 'C1':ROOT/'wp1b_ibm/resolution_crop_v2/C1v2_offset_samples.json',
 'C05':ROOT/'wp1b_ibm/resolution_c05/C05_offset_samples_a_r10.json',
 'C1G0':ROOT/'wp1b_ibm/resolution_split/C1G0_samples.json',
 'B2':ROOT/'wp1b_ibm/inflow_ti/B2_offset_samples.json',
 'G0':ROOT/'wp1_nearwall/city_diag_noT/G0_offset_samples_a_r10.json'}
out={'xls_path':str(XLS),'inflow':{'sampled':[{ 'z':z,'profile':interp(rows,z),'official_interp':interp(official,z),'difference':interp(rows,z)-interp(official,z)} for z in (1.25,2,2.5,5,12.5,15.9,25)],'reference':interp(rows,15.9)},'groups':{},'xls_after_w_means':{}}
for name,path in sources.items():
 d=json.loads(path.read_text());a={v['id']:v for v in d['rows']}; assert len(a)==len(d['rows'])
 for v in a.values():
  assert abs(v['after']-after.cell_value(v['id']+2,14))<1e-9,(name,v['id'],v['after'],after.cell_value(v['id']+2,14))
 assert abs(d['uref']-interp(rows,15.9))<1e-7
 groups={}
 for group,ids in [('open',[23,25,37,17]),('all80',list(range(1,81)))]:
  selected=[a[i] for i in ids if i in a]
  values={quantity:[v['sample']['plus_dx'][key] for v in selected] for quantity,key in [('S','sim_ratio'),('Sstar','exp_ratio')]}
  obs=[v['after'] for v in selected]
  groups[group]={'n':len(selected),'ids':[v['id'] for v in selected],'observation_mean':statistics.mean(obs),'metrics':{q:{'mean':statistics.mean(vals),'mean_ratio':statistics.mean(vals)/statistics.mean(obs),'mae':statistics.mean(abs(x-y) for x,y in zip(vals,obs))} for q,vals in values.items()}}
 out['groups'][name]=groups
out['xls_after_w_means']={g:statistics.mean([after.cell_value(i+2,14) for i in ids]) for g,ids in [('open',[23,25,37,17]),('all80',list(range(1,81)))]}
(R/'audit_metrics.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
