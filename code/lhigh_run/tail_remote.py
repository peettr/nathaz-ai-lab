from pathlib import Path
for n in ('lhigh_d80','lhigh_city_H1','lhigh_city_H2'):
 p=Path('/content')/n
 if p.exists():
  for f in ('solver.log','progress.log'):
   if (p/f).exists():print(n,f,(p/f).read_text()[-1000:])
