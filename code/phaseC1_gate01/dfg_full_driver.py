import os,subprocess,time,traceback
from pathlib import Path
root=Path('/content/dfgv1/FluidX3D');start=time.monotonic()
try:
 for d in (20,40):
  for variant in ('ibb','stair'):
   tag=f'D{d}_{variant}';env=os.environ.copy();env.update(IBB_TEST_KIND='dfg',DFG_D=str(d),DFG_STEPS=str(round(100/.018*d)),DFG_OUT=f'/content/{tag}_full.csv')
   if variant=='ibb':env['LUW_IBB_CSR']=f'/content/dfg_D{d}.csr'
   else:env.pop('LUW_IBB_CSR',None)
   print('START',tag,env['DFG_STEPS'],'elapsed',time.monotonic()-start,flush=True)
   with open(f'/content/{tag}_full_solver.log','w',buffering=1) as f:
    r=subprocess.run([str(root/'bin/FluidX3D')],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1500)
   print('END',tag,'exit',r.returncode,'elapsed',time.monotonic()-start,'csv_bytes',Path(env['DFG_OUT']).stat().st_size if Path(env['DFG_OUT']).exists() else -1,flush=True)
   if r.returncode:break
  if r.returncode:break
except Exception:
 traceback.print_exc()
finally:
 Path('/content/dfg_full.done').write_text('done '+str(time.monotonic()-start))
