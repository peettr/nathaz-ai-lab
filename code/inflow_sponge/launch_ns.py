import subprocess,os
from pathlib import Path
T='FGz2ns'
R=Path('/content/luw_sponge_'+T)
if R.exists():
 print('EXISTS',R)
else:
 with open('/content/sponge_'+T+'.launch','w',buffering=1) as f:
  p=subprocess.Popen(['python3','/content/remote_sponge.py',T],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('LAUNCHED',p.pid)
