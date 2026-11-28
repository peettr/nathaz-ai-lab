import subprocess
from pathlib import Path
p=Path('/content/m6')
assert (p/'train_gfs.done').exists() and (p/'train_gfs.exit').read_text().strip()=='0'
assert len(list((p/'train_gfs').glob('*.csv'))) == 376
s='cd /content/m6; python -u m6_score.py train > train_fit.log 2>&1; echo $? > train_fit.exit; touch train_fit.done'
a=subprocess.Popen(['bash','-lc',s],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('TRAIN_FIT_PID',a.pid)
