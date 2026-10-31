from pathlib import Path
import subprocess
for tag in ('E1Wv2','E1G0','E1G0Wv2'):
 r=Path('/content/luw_keep_'+tag)
 if r.exists():
  for name in ('progress.log','solver.exit','error.txt','extract.log'):
   p=r/name
   if p.exists():print(tag,name,p.read_text(errors='replace')[-1500:])
  p=r/'solver.log'
  if p.exists():print(tag,'solver.log',p.read_text(errors='replace')[-500:])
print('PROC',subprocess.run(['pgrep','-af','remote_keep.py|FluidX3D'],capture_output=True,text=True).stdout[-600:])
