from pathlib import Path
import subprocess
for t in ('FGz2r','FGz2c'):
 r=Path('/content/luw_sponge_'+t)
 print(t,'exists',r.exists())
 for name in ('progress.log','error.txt','solver.exit','all.done'):
  p=r/name
  if p.exists():print(name,p.read_text()[-1200:])
print(subprocess.run(['pgrep','-af','remote_sponge|FluidX3D'],capture_output=True,text=True).stdout[:2000])
