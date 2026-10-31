from pathlib import Path
p=Path('/content/mixing07.log');print('JOB',p.read_text()[-1000:] if p.exists() else 'missing')
q=Path('/content/luw_mixing07/solver.log');print('SOLVER',q.read_text()[-1000:] if q.exists() else 'missing')
for f in ('mixing07.done','mixing07.error'):
 q=Path('/content/luw_mixing07')/f
 if q.exists():print(f,q.read_text()[-2000:])
