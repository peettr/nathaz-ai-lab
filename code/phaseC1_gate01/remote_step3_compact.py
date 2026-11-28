import os,subprocess,time
from pathlib import Path
root=Path('/content/compact/step3_compact_stage');root.parent.mkdir(exist_ok=True)
subprocess.run(['tar','-xzf','/content/step3_compact_stage.tar.gz','-C',str(root.parent)],check=True)
with open('/content/compact_build.log','w') as f:r=subprocess.run(['make','Linux','-j4'],cwd=root,stdout=f,stderr=subprocess.STDOUT)
print('BUILD',r.returncode,flush=True)
if r.returncode:
 print(''.join(open('/content/compact_build.log').readlines()[-50:]),flush=True);raise SystemExit(1)
env=os.environ.copy();env.update(IBB_TEST_KIND='dfg',DFG_D='20',DFG_STEPS=str(round(100/.018*20)),DFG_OUT='/content/compact_D20_full.csv',LUW_IBB_CSR='/content/dfg_D20.csr')
with open('/content/compact_D20.log','w',buffering=1) as f:r=subprocess.run([str(root/'bin/FluidX3D')],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=900)
print('RUN',r.returncode,'bytes',Path(env['DFG_OUT']).stat().st_size if Path(env['DFG_OUT']).exists() else -1,flush=True)
Path('/content/compact.done').write_text(str(r.returncode))