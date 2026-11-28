import subprocess
from pathlib import Path
p=Path('/content/m5/train_gfs.launch')
with p.open('x') as f:f.write('R23.2 M5 full GFS train\n')
a=subprocess.Popen(['bash','/content/m5/train_gfs.sh'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('TRAIN_GFS_PID',a.pid)
