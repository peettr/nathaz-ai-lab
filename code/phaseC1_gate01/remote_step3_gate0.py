import os,subprocess,time
from pathlib import Path
root=Path('/content/step3/dfg_laminar_stage_FluidX3D')
root.parent.mkdir(exist_ok=True)
subprocess.run(['tar','-xzf','/content/dfg_laminar_stage.tar.gz','-C',str(root.parent)],check=True)
with open('/content/step3_build.log','w') as f:r=subprocess.run(['make','Linux','-j4'],cwd=root,stdout=f,stderr=subprocess.STDOUT)
print('BUILD',r.returncode,flush=True)
if r.returncode:print(''.join(open('/content/step3_build.log').readlines()[-30:]));raise SystemExit(1)
t0=time.monotonic()
for q in (.25,.75):
 for nz in (10,20,40):
  h0=7.5+q;h=nz-2.5+q;ratio=h/h0;nu=.1*ratio;force=.16*nu/h**2
  tag=f'z{nz}_q{str(q).replace(".","p")}'
  env=os.environ.copy();env.update(IBB_NZ=str(nz),IBB_NU=str(nu),IBB_FORCE=str(force),IBB_TEST_KIND='poiseuille',IBB_TEST_STEPS=str(round(16000*ratio)),IBB_TEST_OUT=f'/content/step3_{tag}.csv',LUW_IBB_CSR=f'/content/step3_floor_{tag}.csr')
  with open(f'/content/step3_{tag}.log','w') as f:r=subprocess.run([str(root/'bin/FluidX3D')],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=240)
  print(tag,nu,force,'exit',r.returncode,'elapsed',round(time.monotonic()-t0,2),flush=True)
  if r.returncode:print(''.join(open(f'/content/step3_{tag}.log').readlines()[-20:]));raise SystemExit(2)
Path('/content/step3.done').write_text('done')