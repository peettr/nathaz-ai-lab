import os
from pathlib import Path
for name in ('H1','H2','D80'):
 for prefix in ('m1city2_','m1city_'):
  p=Path('/content')/(prefix+name)
  if p.exists():
   print(name,p.name,'done',(p/'all.done').exists())
   for f in ('progress.log','error.txt','solver.exit'):
    if (p/f).exists():print(f,(p/f).read_text()[-1200:])
