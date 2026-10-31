"""Analyze the Colab-only fixed-viscosity IBB runs, retaining raw files."""
from pathlib import Path
import zipfile,csv,json,numpy as np
R=Path(__file__).resolve().parent
out=R/'step4_fixednu_results';out.mkdir(exist_ok=True)
with zipfile.ZipFile(R/'step4_results.zip') as z:z.extractall(out)
res={}
for q in (.25,.75):
 for nz in (10,20,40):
  for nu in ((.1,.25,.5) if nz==20 and q==.25 else (.1,)):
   tag=f'z{nz}_q{str(q).replace(".","p")}_nu{str(nu).replace(".","p")}'
   rows=list(csv.reader((out/(tag+'.csv')).open()))
   z=np.array([float(r[1]) for r in rows if r[0]=='PROFILE' and r[1]!='z']);u=np.array([float(r[2]) for r in rows if r[0]=='PROFILE' and r[1]!='z'])
   assert len(z)>0,tag
   h=nz-2.5+q;f=.16*nu/h**2
   exact=f/(2*nu)*(z-(1-q))*(nz-1.5-z)
   coef=np.polyfit(z,u,2);roots=np.sort(np.roots(coef)).real
   res[tag]={'nu':nu,'force':f,'umax_analytic':float(max(exact)),'absolute_L2':float(np.sqrt(np.mean((u-exact)**2))),'relative_L2':float(np.linalg.norm(u-exact)/np.linalg.norm(exact)),'fit_wall_offset_cells':float(roots[0]-(1-q)),'fit_upper_wall_offset_cells':float(roots[1]-(nz-1.5)),'fit_residual_L2':float(np.sqrt(np.mean((u-np.polyval(coef,z))**2))),'fallback':[r[1:] for r in rows if r[0]=='FALLBACK']}
 for n0,n1 in ((10,20),(20,40)):
  tag=lambda n:f'z{n}_q{str(q).replace(".","p")}_nu0p1'
  h0=n0-2.5+q;h1=n1-2.5+q
  import math
  res[f'order_q{q}_{n0}_{n1}']=math.log(res[tag(n0)]['relative_L2']/res[tag(n1)]['relative_L2'])/math.log(h1/h0)
 tag=lambda n:f'z{n}_q{str(q).replace(".","p")}_nu0p1'
 res[f'order_q{q}_fit3']=-float(np.polyfit(np.log([n-2.5+q for n in (10,20,40)]),np.log([res[tag(n)]['relative_L2'] for n in (10,20,40)]),1)[0])
(out/'metrics.json').write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps(res,indent=2))
