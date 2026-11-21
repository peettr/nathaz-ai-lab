import csv,json,math
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent/'step3_gate0_results';result={}
for q in (.25,.75):
 for nz in (10,20,40):
  tag=f'z{nz}_q{str(q).replace(".","p")}'
  rows=list(csv.reader((p/(tag+'.csv')).open()))
  z=np.array([float(r[1]) for r in rows if r[0]=='PROFILE' and r[1]!='z']);u=np.array([float(r[2]) for r in rows if r[0]=='PROFILE' and r[1]!='z'])
  h=nz-2.5+q;nu=.1*h/(7.5+q);f=.16*nu/h**2
  exact=f/(2*nu)*(z-(1-q))*(nz-1.5-z)
  err=u-exact;coef=np.polyfit(z,u,2);roots=np.sort(np.roots(coef)).real
  result[tag]={'nu':nu,'force':f,'umax_analytic':float(max(exact)),'absolute_L2':float(np.sqrt(np.mean(err**2))),'relative_L2':float(np.linalg.norm(err)/np.linalg.norm(exact)),'fit_wall_offset_cells':float(roots[0]-(1-q)),'fit_upper_wall_offset_cells':float(roots[1]-(nz-1.5)),'fit_residual_L2':float(np.sqrt(np.mean((u-np.polyval(coef,z))**2))),'fallback':[r[1:] for r in rows if r[0]=='FALLBACK']}
 vals=[result[f'z{n}_q{str(q).replace(".","p")}']['relative_L2'] for n in (10,20,40)]
 h=np.array([n-2.5+q for n in (10,20,40)])
 result[f'order_q{q}']={'pair_10_20':float(np.log(vals[0]/vals[1])/np.log(h[1]/h[0])),'pair_20_40':float(np.log(vals[1]/vals[2])/np.log(h[2]/h[1])),'fit_3point':float(-np.polyfit(np.log(h),np.log(vals),1)[0])}
(p/'metrics.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))