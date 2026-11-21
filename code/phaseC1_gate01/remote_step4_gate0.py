# Run fixed-viscosity IBB channels on Colab A100; no local solver.
import os, subprocess, time, tarfile
from pathlib import Path
root=Path('/content/step4/dfg_laminar_stage_FluidX3D');root.parent.mkdir(exist_ok=True)
with tarfile.open('/content/dfg_laminar_stage.tar.gz') as t:t.extractall(root.parent,filter='data')
with open('/content/step4_build.log','w') as log:r=subprocess.run(['make','Linux','-j4'],cwd=root,stdout=log,stderr=subprocess.STDOUT)
print('BUILD',r.returncode,flush=True)
if r.returncode:print(''.join(open('/content/step4_build.log').readlines()[-25:]));raise SystemExit(1)
for q,nz,nu in [(q,nz,.1) for q in (.25,.75) for nz in (10,20,40)]+[(.25,20,nu) for nu in (.25,.5)]:
 h=nz-2.5+q;force=.16*nu/h**2;tag=f'z{nz}_q{str(q).replace(".","p")}_nu{str(nu).replace(".","p")}'
 env=os.environ.copy();env.update(IBB_NZ=str(nz),IBB_NU=str(nu),IBB_FORCE=str(force),IBB_TEST_KIND='poiseuille',IBB_TEST_STEPS=str(round(16000*(h/(7.5+q))**2)),IBB_TEST_OUT=f'/content/{tag}.csv',LUW_IBB_CSR=f'/content/step3_floor_z{nz}_q{str(q).replace(".","p")}.csr')
 t0=time.monotonic()
 with open(f'/content/{tag}.log','w') as log:r=subprocess.run([str(root/'bin/FluidX3D')],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
 print(tag,'nu',nu,'F',force,'steps',env['IBB_TEST_STEPS'],'exit',r.returncode,'seconds',round(time.monotonic()-t0,2),flush=True)
 if r.returncode:print(''.join(open(f'/content/{tag}.log').readlines()[-20:]));raise SystemExit(2)
Path('/content/step4.done').write_text('done')
