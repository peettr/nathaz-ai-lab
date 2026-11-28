import subprocess
from pathlib import Path
print(subprocess.run(['ps','-eo','pid,ppid,stat,etime,args'],capture_output=True,text=True).stdout[-12000:])
for root in (Path('/content/a170_2/results'),Path('/content/a170_2/runs')):
 print('root',root,'exists',root.exists())
 if root.exists():
  for x in list(root.iterdir())[-12:]:print(x.name,x.stat().st_size)
