from pathlib import Path
for t in ('E1G0A35','E1G0A70'):
 r=Path('/content/luw_keep2_'+t)
 for n in ('progress.log','solver.exit','extract.log','error.txt'):
  p=r/n
  if p.exists():print(t,n,p.read_text(errors='replace')[-700:])
