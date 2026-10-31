import subprocess
from pathlib import Path
p=Path('/content/m6')
s="cd /content/m6; M6_LIMIT=1 python -u m6_extract.py train > pilot.log 2>&1; echo $? > pilot.exit; touch pilot.done"
a=subprocess.Popen(['bash','-lc',s],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('PILOT_PID',a.pid)
