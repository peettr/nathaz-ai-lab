import os, subprocess, time
from pathlib import Path
root=Path('/content/FluidX3D')
subprocess.run(['tar','-xzf','/content/ibb_gate0_v3_stage.tar.gz','-C','/content'],check=True)
with open('/content/build_gate0_v3.log','w') as f:
 r=subprocess.run(['make','Linux','-j4'],cwd=root,stdout=f,stderr=subprocess.STDOUT)
print('BUILD_EXIT',r.returncode,flush=True)
if r.returncode: print(''.join(open('/content/build_gate0_v3.log').readlines()[-40:]));raise SystemExit(1)
for nz,q,kind,steps in [(10,.25,'poiseuille',12000),(10,.75,'poiseuille',12000),(20,.25,'poiseuille',40000),(20,.75,'poiseuille',40000),(20,None,'closed',2000)]:
 tag=f'z{nz}_q{str(q).replace(".","p")}' if q is not None else 'closed_z20'
 env=os.environ.copy();env['IBB_NZ']=str(nz);env['IBB_TEST_KIND']=kind;env['IBB_TEST_STEPS']=str(steps)
 env['IBB_TEST_OUT']=f'/content/gate0_{tag}.csv'
 env['LUW_IBB_CSR']=f'/content/gate0_bottom_{tag}.csr' if q is not None else '/content/gate0_closed_z20.csr'
 t=time.monotonic()
 with open(f'/content/gate0_{tag}.log','w') as f:
  r=subprocess.run([str(root/'bin/FluidX3D')],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1800)
 print('CASE',tag,'EXIT',r.returncode,'SECONDS',round(time.monotonic()-t,2),'CSV',Path(env['IBB_TEST_OUT']).stat().st_size if Path(env['IBB_TEST_OUT']).exists() else -1,flush=True)
 if r.returncode:print(''.join(open(f'/content/gate0_{tag}.log').readlines()[-25:]));break
