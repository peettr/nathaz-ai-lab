from pathlib import Path
import subprocess
r=Path('/content/r234c_gc37x_B1')
for n in ['worker_gc37x_B1_four_v1.log','launcher_stdout.log','worker_gc37x_B1_four_v1.done','worker_gc37x_B1_four_v1.failed']:
 p=r/n
 print(n,'exists',p.exists(),'bytes',p.stat().st_size if p.exists() else None)
 if p.exists() and p.stat().st_size<200000:
  print('\n'.join(p.read_text(errors='replace').splitlines()[-12:]))
print(subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.used','--format=csv,noheader'],capture_output=True,text=True).stdout)
