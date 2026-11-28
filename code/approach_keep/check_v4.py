from pathlib import Path
import subprocess
for tag in ('E1Wv4','E1G0','E1G0Wv4'):
 r=Path('/content/luw_keep_'+tag)
 if r.exists():
  for name in ('progress.log','solver.exit','error.txt','extract.log'):
   p=r/name
   if p.exists():print(tag,name,p.read_text(errors='replace')[-1200:])
  p=r/'solver.log'
  if p.exists():print(tag,'solver.log',p.read_text(errors='replace')[-700:])
print('PROC',subprocess.run(['pgrep','-af','remote_keep.py|FluidX3D'],capture_output=True,text=True).stdout[-600:])
