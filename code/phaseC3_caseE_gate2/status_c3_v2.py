from pathlib import Path
r=Path('/content/luw_c3_gate2_v2_1016')
for p in [r/'progress.log',r/'H1/solver.log',r/'H2/solver.log',r/'error.txt']:
 if p.exists():
  s=p.read_text(errors='replace');print('\n',p.name,'bytes',len(s),'tail',s[-1300:])
