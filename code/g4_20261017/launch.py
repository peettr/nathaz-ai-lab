from pathlib import Path
import subprocess,sys,os,time
root=Path('/content/g4_persist')
root.mkdir(exist_ok=True)
marker=root/'runner.started'
with marker.open('x') as f:f.write(str(time.time()))
with (root/'supervisor.log').open('x') as log:
 p=subprocess.Popen([sys.executable,str(root/'supervisor.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,cwd='/content')
print('launched pid',p.pid,flush=True)
