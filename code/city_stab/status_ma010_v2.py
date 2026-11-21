from pathlib import Path
import time,re
r=Path('/content/luw_city_ma010_v2_1016')
for name in ('progress.log','solver.exit','error.txt'):
 p=r/name
 print(name,p.exists(),p.read_bytes()[-900:].decode(errors='replace') if p.exists() else '')
p=r/'solver.log'
if p.exists():
 s=p.read_bytes()[-10000:].decode(errors='replace')
 print('solver log tail',s[-400:])
print('remaining',float(Path('/content/ma010_deadline_epoch.txt').read_text())-time.time())
