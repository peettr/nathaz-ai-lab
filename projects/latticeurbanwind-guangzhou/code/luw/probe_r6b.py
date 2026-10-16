from pathlib import Path
r=Path('/content/luw-aij-r6b')
for name in ('solver.metrics','solver.exit','solver_wrapper.log'):
 p=r/name
 print(name,p.read_text()[-400:] if p.exists() else 'absent',flush=True)
p=r/'solver.log'
if p.exists():
 lines=p.read_text(errors='replace').splitlines()
 print('LOG_LAST', '\n'.join(lines[-6:])[-1500:],flush=True)
