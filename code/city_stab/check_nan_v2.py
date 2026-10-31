from pathlib import Path
R=Path('/content/luw_nan_stage4_v2_1016')
for name in ['progress.log','error.txt','solver.exit','case/RESULTS/nan_event.txt','case/RESULTS/nan_history.csv','case/RESULTS/nan_neighborhood.csv','all.done']:
 p=R/name
 print(name,p.exists(),p.stat().st_size if p.exists() else '',(p.read_text(errors='replace')[-1000:] if p.exists() and p.stat().st_size<100000 else ''),flush=True)
log=R/'solver.log'
if log.exists():
 import re
 s=log.read_text(errors='replace')
 print('solver_bytes',len(s),'tail',repr(s[-350:]),flush=True)
