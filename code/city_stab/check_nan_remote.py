from pathlib import Path
R=Path('/content/luw_nan_stage4_retry3_1016')
for name in ['progress.log','build.log','error.txt','solver.log','case/RESULTS/nan_event.txt','all.done']:
 p=R/name
 print(name,p.exists(),p.stat().st_size if p.exists() else '',(p.read_text(errors='replace')[-1800:] if p.exists() else ''),flush=True)
