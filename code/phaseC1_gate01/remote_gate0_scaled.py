import os,subprocess,time
from pathlib import Path
root=Path('/content/gate0scale/dfg_laminar_stage_FluidX3D');root.parent.mkdir(exist_ok=True)
subprocess.run(['tar','-xzf','/content/dfg_laminar_stage.tar.gz','-C',str(root.parent)],check=True)
with open('/content/gate0scale_build.log','w') as f:r=subprocess.run(['make','Linux','-j4'],cwd=root,stdout=f,stderr=subprocess.STDOUT)
print('BUILD',r.returncode,flush=True)
if r.returncode:print(''.join(open('/content/gate0scale_build.log').readlines()[-30:]));raise SystemExit(1)
for q in (.25,.75):
 for nz in (10,18):
  h0=7.5+q;h=nz-2.5+q;ratio=h/h0;nu=.1*ratio;force=2e-6/ratio
  tag=f'z{nz}_q{str(q).replace(".","p")}';env=os.environ.copy();env.update(IBB_NZ=str(nz),IBB_NU=str(nu),IBB_FORCE=str(force),IBB_TEST_KIND='poiseuille',IBB_TEST_STEPS='12000' if nz==10 else '40000',IBB_TEST_OUT=f'/content/scale_{tag}.csv',LUW_IBB_CSR=f'/content/gate0_bottom_{tag}.csr')
  with open(f'/content/scale_{tag}.log','w') as f:r=subprocess.run([str(root/'bin/FluidX3D')],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=300)
  print(tag,nu,force,'exit',r.returncode,flush=True)
  if r.returncode:print(''.join(open(f'/content/scale_{tag}.log').readlines()[-30:]));raise SystemExit(2)
