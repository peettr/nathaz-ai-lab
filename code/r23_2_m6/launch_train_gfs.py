import subprocess
from pathlib import Path
p=Path('/content/m6')
s='cd /content/m6; python -u m6_extract.py train > train_gfs.log 2>&1; echo $? > train_gfs.exit; touch train_gfs.done'
a=subprocess.Popen(['bash','-lc',s],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('TRAIN_GFS_PID',a.pid)
