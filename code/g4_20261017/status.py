import os,json,subprocess
from pathlib import Path
for p in ['/content/g4_persist/runner.exit','/content/results/runner.log','/content/Strata/engine/strata','/content/Strata-data/packs/unsloth-ud-iq4_xs/dense.bin']:
 x=Path(p); print(p, 'bytes='+str(x.stat().st_size) if x.exists() else 'missing')
 if p.endswith('runner.exit') and x.exists(): print('exit',x.read_text())
p=Path('/content/results/runner.log')
if p.exists():print('tail', '\n'.join(p.read_text(errors='replace').splitlines()[-12:]))
print('disk',subprocess.run(['df','-h','/content'],capture_output=True,text=True).stdout)
