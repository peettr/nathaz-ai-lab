import os
from pathlib import Path
for name in ('lhigh_d80','lhigh_city_H1','lhigh_city_H2'):
 p=Path('/content')/name
 if p.exists():
  print(name,'done',(p/'all.done').exists(),'complete',(p/'complete.txt').exists())
  for f in ('progress.log','error.txt','latest.json'):
   if (p/f).exists():print(f,(p/f).read_text()[-1200:])
