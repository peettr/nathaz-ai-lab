from pathlib import Path
p=Path('/content/stress.log');print(p.read_text()[-2500:] if p.exists() else 'no log')
q=Path('/content/luw_stress/diagnostic/solver.log');print('SOLVER',q.read_text()[-1800:] if q.exists() else 'missing')
q=Path('/content/luw_mixing/solver.log');print('MIX_SOLVER',q.read_text()[-800:] if q.exists() else 'missing')
for f in ('mixing.done','mixing.error'):
 q=Path('/content/luw_mixing')/f
 if q.exists():print(f,q.read_text()[-2500:])
