from pathlib import Path
import subprocess,json
r=Path('/content/t3_run2_smoke/evidence')
print('SMOKE_FILES',[(p.name,p.stat().st_size) for p in sorted(r.glob('*'))] if r.exists() else 'none')
for n in ('error.log','exit.json','solver.log','build.log'):
 p=r/n
 if p.exists():print(n,'TAIL',p.read_text(errors='replace')[-1800:])
print('PROCS',subprocess.run(['pgrep','-af','smoke_worker.py'],capture_output=True,text=True).stdout[-300:])
