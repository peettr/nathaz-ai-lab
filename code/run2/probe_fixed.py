from pathlib import Path
r=Path('/content/t3_run2_smoke_fixed/evidence')
print('FIXED_SMOKE_FILES',[(p.name,p.stat().st_size) for p in sorted(r.glob('*'))] if r.exists() else [])
for n in ('error.log','exit.json','solver.log'):
 p=r/n
 if p.exists():print(n,'TAIL',p.read_text(errors='replace')[-1800:])
