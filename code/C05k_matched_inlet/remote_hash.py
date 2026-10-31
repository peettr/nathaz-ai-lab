from pathlib import Path
import hashlib
r=Path('/content/c05k_gate_01')
for n in ('gate_profiles.json','solver.exit','progress.log','solver.log','build.log'):
 p=r/n;print(n,p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest())
