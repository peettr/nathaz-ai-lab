import os,subprocess
from pathlib import Path
subprocess.run(['tar','-xzf','/content/ibb_fallback_stage.tar.gz','-C','/content'],check=True)
root=Path('/content/FluidX3D');
with open('/content/fallback_build.log','w') as f:r=subprocess.run(['make','Linux','-j4'],cwd=root,stdout=f,stderr=subprocess.STDOUT)
print('BUILD',r.returncode,flush=True)
if r.returncode:print(''.join(open('/content/fallback_build.log').readlines()[-25:]));raise SystemExit(1)
e=os.environ.copy();e.update(IBB_NZ='10',IBB_TEST_KIND='poiseuille',IBB_TEST_STEPS='200',IBB_FORCE_FALLBACK='1',IBB_TEST_OUT='/content/fallback_result.csv',LUW_IBB_CSR='/content/gate0_bottom_z10_q0p25.csr')
with open('/content/fallback_solver.log','w') as f:r=subprocess.run([str(root/'bin/FluidX3D')],cwd=root,env=e,stdout=f,stderr=subprocess.STDOUT)
print('RUN',r.returncode,[v for v in open('/content/fallback_result.csv') if v.startswith('FALLBACK,')] if Path('/content/fallback_result.csv').exists() else None,flush=True)
