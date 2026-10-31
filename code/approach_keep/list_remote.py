from pathlib import Path
for tag in ('E1G0','E1Wv5'):
 r=Path('/content/luw_keep_'+tag)
 for p in [r/'offset_samples_a_r10.json',r/'case/RESULTS/wall_tau_actual.csv',r/'case/RESULTS/city_stability.csv',r/'progress.log',r/'solver.log',r/'solver.exit',r/'build.log']:
  if p.exists():print(tag,str(p),p.stat().st_size)
