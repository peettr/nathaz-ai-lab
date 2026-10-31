import os,subprocess,time,tarfile,json,csv,zipfile,traceback
from pathlib import Path
import numpy as np
R=Path('/content/lhigh_regression');R.mkdir(exist_ok=False)
def log(s):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(s)+'\n')
 print(s,flush=True)
try:
 with tarfile.open('/content/lhigh_dfg_fixture.tar.gz') as t:t.extractall(R,filter='data')
 root=R/'dfg_laminar_stage_FluidX3D'
 with (R/'build.log').open('w') as f:b=subprocess.run(['make','Linux','-j4'],cwd=root,stdout=f,stderr=subprocess.STDOUT,timeout=400)
 log('BUILD '+str(b.returncode))
 if b.returncode:raise RuntimeError((R/'build.log').read_text()[-3000:])
 import math
 metrics={}
 for q in (.25,.75):
  for nz in (10,20,40):
   h=nz-2.5+q;nu=.1;force=.16*nu/h**2;tag=f'z{nz}_q{str(q).replace(".","p")}'
   env=os.environ.copy();env.update(IBB_NZ=str(nz),IBB_NU=str(nu),IBB_FORCE=str(force),IBB_TEST_KIND='poiseuille',IBB_TEST_STEPS=str(round(16000*(h/(7.5+q))**2)),IBB_TEST_OUT=str(R/(tag+'.csv')),LUW_IBB_CSR=f'/content/step3_floor_z{nz}_q{str(q).replace(".","p")}.csr')
   t0=time.monotonic()
   with (R/(tag+'.log')).open('w') as f:p=subprocess.run([str(root/'bin/FluidX3D')],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=300)
   log(tag+' exit='+str(p.returncode)+' sec='+str(round(time.monotonic()-t0,2)))
   if p.returncode:raise RuntimeError((R/(tag+'.log')).read_text()[-1500:])
   rows=list(csv.reader((R/(tag+'.csv')).open()))
   z=np.array([float(r[1]) for r in rows if r[0]=='PROFILE' and r[1]!='z']);u=np.array([float(r[2]) for r in rows if r[0]=='PROFILE' and r[1]!='z'])
   exact=force/(2*nu)*(z-(1-q))*(nz-1.5-z);roots=np.sort(np.roots(np.polyfit(z,u,2))).real
   metrics[tag]={'absolute_L2':float(np.sqrt(np.mean((u-exact)**2))),'relative_L2':float(np.linalg.norm(u-exact)/np.linalg.norm(exact)),'lower_wall_offset':float(roots[0]-(1-q)),'upper_wall_offset':float(roots[1]-(nz-1.5))}
  for n0,n1 in [(10,20),(20,40)]:
   key=lambda n:f'z{n}_q{str(q).replace(".","p")}'
   metrics[f'order_q{q}_{n0}_{n1}']=math.log(metrics[key(n0)]['relative_L2']/metrics[key(n1)]['relative_L2'])/math.log((n1-2.5+q)/(n0-2.5+q))
  keys=[f'z{n}_q{str(q).replace(".","p")}' for n in (10,20,40)]
  metrics[f'order_q{q}_fit3']=-float(np.polyfit(np.log([n-2.5+q for n in (10,20,40)]),np.log([metrics[k]['relative_L2'] for k in keys]),1)[0])
 (R/'channel_metrics.json').write_text(json.dumps(metrics,indent=2))
 env=os.environ.copy();env.update(IBB_TEST_KIND='dfg',DFG_D='40',DFG_STEPS=str(round(100/.018*40)),DFG_OUT=str(R/'lam_D40_ibb_full.csv'),LUW_IBB_CSR='/content/dfg_D40.csr')
 t0=time.monotonic();log('DFG start')
 with (R/'dfg_solver.log').open('w',buffering=1) as f:p=subprocess.run([str(root/'bin/FluidX3D')],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=600)
 log('DFG exit='+str(p.returncode)+' sec='+str(round(time.monotonic()-t0,2)))
 if p.returncode:raise RuntimeError((R/'dfg_solver.log').read_text()[-1500:])
 # Preserve raw; compute metrics using same protocol as frozen analyzer.
 import scipy.signal as signal
 data=np.genfromtxt(R/'lam_D40_ibb_full.csv',delimiter=',',names=True)
 log('DFG columns '+str(data.dtype.names)+' rows '+str(len(data)))
 (R/'complete.txt').write_text('complete\n')
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log(traceback.format_exc()[-2500:])
finally:
 with zipfile.ZipFile('/content/lhigh_regression.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
  for p in R.iterdir():
   if p.is_file():z.write(p,p.name)
 (R/'all.done').write_text('done\n')
