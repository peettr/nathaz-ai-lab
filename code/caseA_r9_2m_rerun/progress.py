from pathlib import Path
import time,subprocess
r=Path('/content/luw-aij-caseA-turb-20261014')
for n in ('solver.log','solver.metrics','solver.exit','caseA/RESULTS/vtk'):
 p=r/n;print(n,p.exists(),p.stat().st_size if p.exists() and p.is_file() else '',p.stat().st_mtime if p.exists() else '')
print('tail', '\n'.join((r/'solver.log').read_text(errors='replace').splitlines()[-12:]))
print(subprocess.run(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu','--format=csv,noheader'],capture_output=True,text=True).stdout)
