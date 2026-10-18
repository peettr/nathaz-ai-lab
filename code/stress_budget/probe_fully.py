from pathlib import Path
p=Path('/content/fully.log');print('JOB',p.read_text()[-1200:] if p.exists() else 'missing')
q=Path('/content/luw_fully/solver.log');print('SOLVER',q.read_text()[-800:] if q.exists() else 'missing')
for f in ('fully.done','fully.error'):
 q=Path('/content/luw_fully')/f
 if q.exists():print(f,q.read_text()[-2000:])
