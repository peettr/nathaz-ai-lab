from pathlib import Path
import zipfile
r=Path('/content/luw_c3_bisect_v5_1016')
with zipfile.ZipFile('/content/bisect_v5_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in [r/'progress.log',r/'error.txt']+list(r.glob('B*/event.csv'))+list(r.glob('B*/solver.exit'))+list(r.glob('B*/solver.log'))+list(r.glob('B*/case/RESULTS/city_stability.csv')):
  if p.exists():z.write(p,p.relative_to(r))
print('evidence bytes',Path('/content/bisect_v5_evidence.zip').stat().st_size)
