import subprocess,os,time
from pathlib import Path
root=Path('/content/dfgv1/FluidX3D');root.parent.mkdir(exist_ok=True)
subprocess.run(['tar','-xzf','/content/ibb_dfg_v1_stage.tar.gz','-C',str(root.parent)],check=True)
with open('/content/dfgv1_build.log','w') as f:r=subprocess.run(['make','Linux','-j4'],cwd=root,stdout=f,stderr=subprocess.STDOUT)
print('BUILD',r.returncode,flush=True)
if r.returncode:print(''.join(open('/content/dfgv1_build.log').readlines()[-30:]));raise SystemExit(1)
for d in (20,40):
 for variant in ('ibb','stair'):
  tag=f'D{d}_{variant}_smoke';env=os.environ.copy();env.update(IBB_TEST_KIND='dfg',DFG_D=str(d),DFG_STEPS='100',DFG_OUT=f'/content/{tag}.csv')
  if variant=='ibb':env['LUW_IBB_CSR']=f'/content/dfg_D{d}.csr'
  else:env.pop('LUW_IBB_CSR',None)
  with open(f'/content/{tag}.log','w') as f:r=subprocess.run([str(root/'bin/FluidX3D')],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=300)
  print(tag,'exit',r.returncode,'csv',Path(env['DFG_OUT']).stat().st_size if Path(env['DFG_OUT']).exists() else -1,flush=True)
  if r.returncode:print(''.join(open(f'/content/{tag}.log').readlines()[-25:]));raise SystemExit(2)
