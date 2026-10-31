from pathlib import Path
import zipfile
r=Path('/content/luw_c3_linear_1016')
with zipfile.ZipFile('/content/linear_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in [r/'progress.log',r/'error.txt']+list(r.glob('L*/event.csv'))+list(r.glob('L*/solver.exit'))+list(r.glob('L*/solver.log'))+list(r.glob('L*/case/RESULTS/city_stability.csv')):
  if p.exists():z.write(p,p.relative_to(r))
print('bytes',Path('/content/linear_evidence.zip').stat().st_size)
