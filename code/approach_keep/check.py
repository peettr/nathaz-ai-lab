from pathlib import Path
import subprocess
for tag in ('E1W','E1G0','E1G0W'):
 r=Path('/content/luw_keep_'+tag)
 if r.exists():
  for name in ('progress.log','build.log','solver.exit','error.txt','extract.log'):
   p=r/name
   if p.exists():
    s=p.read_text(errors='replace')
    print(tag,name,s[-1400:])
print('PROC',subprocess.run(['pgrep','-af','remote_keep.py|FluidX3D'],capture_output=True,text=True).stdout[-800:])
