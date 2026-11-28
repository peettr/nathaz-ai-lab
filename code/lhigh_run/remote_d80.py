import os,subprocess,time,tarfile,traceback,zipfile
from pathlib import Path
R=Path('/content/lhigh_d80');R.mkdir(exist_ok=False)
def log(s):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(s)+'\n')
 print(s,flush=True)
try:
 with tarfile.open('/content/lhigh_fixed_fixture.tar.gz') as t:t.extractall(R,filter='data')
 root=R/'dfg_laminar_stage_FluidX3D'
 with (R/'build.log').open('w') as f:b=subprocess.run(['make','Linux','-j4'],cwd=root,stdout=f,stderr=subprocess.STDOUT,timeout=500)
 log('BUILD '+str(b.returncode))
 if b.returncode:raise RuntimeError((R/'build.log').read_text()[-2500:])
 env=os.environ.copy();env.update(IBB_TEST_KIND='dfg',DFG_D='80',DFG_STEPS=str(round(100/.018*80)),DFG_OUT=str(R/'lam_D80_ibb_full.csv'),LUW_IBB_CSR='/content/dfg_D80.csr')
 start=time.monotonic();log('DFG D80 start')
 with (R/'solver.log').open('w',buffering=1) as f:p=subprocess.run([str(root/'bin/FluidX3D')],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1500)
 log('DFG D80 exit='+str(p.returncode)+' sec='+str(round(time.monotonic()-start)))
 if p.returncode:raise RuntimeError((R/'solver.log').read_text()[-2000:])
 (R/'complete.txt').write_text('complete\n')
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log(traceback.format_exc()[-3000:])
finally:
 with zipfile.ZipFile('/content/lhigh_d80_evidence.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
  for p in R.iterdir():
   if p.is_file():z.write(p,p.name)
 (R/'all.done').write_text('done\n')
