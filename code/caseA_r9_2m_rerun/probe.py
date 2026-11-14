import os,subprocess
from pathlib import Path
p=Path('/content/luw-aij-caseA-turb-20261014')
print('exists',p.exists(),'repo', (p/'repo/.git').exists(),'binary',(p/'repo/core/cfd_core/FluidX3D/bin/FluidX3D').exists(),'conf',(p/'caseA/conf.luwpf').exists());print('head',subprocess.run(['git','rev-parse','HEAD'],cwd=p/'repo',capture_output=True,text=True).stdout.strip())
print(subprocess.run(['ps','-eo','pid,etime,args'],capture_output=True,text=True).stdout[-3500:])
