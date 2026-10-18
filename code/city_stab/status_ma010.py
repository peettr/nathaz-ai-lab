from pathlib import Path
import time
r=Path('/content/luw_city_ma010_1016')
for name in ('progress.log','build.log','solver.exit','error.txt'):
 p=r/name
 print(name,p.exists(), p.read_bytes()[-700:].decode(errors='replace') if p.exists() else '')
print('remaining',float(Path('/content/ma010_deadline_epoch.txt').read_text())-time.time())
