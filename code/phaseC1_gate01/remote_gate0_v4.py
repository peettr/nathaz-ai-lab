import os,subprocess,time
from pathlib import Path
root=Path('/content/v4/FluidX3D');root.parent.mkdir(exist_ok=True)
subprocess.run(['tar','-xzf','/content/ibb_gate0_v4_stage.tar.gz','-C',str(root.parent)],check=True)
with open('/content/v4_build.log','w') as f:r=subprocess.run(['make','Linux','-j4'],cwd=root,stdout=f,stderr=subprocess.STDOUT)
print('BUILD',r.returncode,flush=True)
if r.returncode:print(''.join(open('/content/v4_build.log').readlines()[-35:]));raise SystemExit(1)
for nz,q,steps in [(10,.25,12000),(10,.75,12000),(20,.25,40000),(20,.75,40000),(20,None,2000)]:
 tag=f'z{nz}_q{str(q).replace(".","p")}' if q is not None else 'closed_z20'
 env=os.environ.copy();env.update(IBB_NZ=str(nz),IBB_TEST_KIND='poiseuille' if q is not None else 'closed',IBB_TEST_STEPS=str(steps),IBB_TEST_OUT=f'/content/v4_{tag}.csv',LUW_IBB_CSR=f'/content/gate0_bottom_{tag}.csr' if q is not None else '/content/gate0_closed_z20.csr')
 t=time.monotonic()
 with open(f'/content/v4_{tag}.log','w') as f:r=subprocess.run([str(root/'bin/FluidX3D')],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1800)
 print(tag,'exit',r.returncode,'seconds',round(time.monotonic()-t,2),flush=True)
 if r.returncode:print(''.join(open(f'/content/v4_{tag}.log').readlines()[-35:]));break
