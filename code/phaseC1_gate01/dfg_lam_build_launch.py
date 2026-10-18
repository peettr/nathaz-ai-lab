import subprocess
from pathlib import Path
subprocess.run(['tar','-xzf','/content/dfg_laminar_stage.tar.gz','-C','/content'],check=True)
root=Path('/content/dfg_laminar_stage_FluidX3D')
with open('/content/dfg_lam_build.log','w') as f:r=subprocess.run(['make','Linux','-j4'],cwd=root,stdout=f,stderr=subprocess.STDOUT)
print('BUILD',r.returncode,flush=True)
if r.returncode:print(''.join(open('/content/dfg_lam_build.log').readlines()[-30:]));raise SystemExit(1)
p=subprocess.Popen(['python3','-u','/content/dfg_lam_driver.py'],stdin=subprocess.DEVNULL,stdout=open('/content/dfg_lam_progress.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('DFG_LAM_PID',p.pid,flush=True)
