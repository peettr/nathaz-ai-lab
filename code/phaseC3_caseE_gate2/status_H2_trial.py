from pathlib import Path
r=Path('/content/luw_c3_gate2_v2_1016/H2_trial')
for p in [r/'progress.log',r/'solver.log',r/'error.txt']:
 if p.exists():
  s=p.read_text(errors='replace');print(p.name,len(s),s[-1000:])
