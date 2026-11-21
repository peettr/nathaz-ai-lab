import subprocess
from pathlib import Path
p=Path('/content/m6')
assert (p/'train_fit.exit').read_text().strip()=='1'
assert (p/'train_gfs.exit').read_text().strip()=='0'
assert len(list((p/'train_gfs').glob('*.csv')))==376
s='cd /content/m6; while true; do date -u +"%Y-%m-%d %H:%M:%S UTC waiting for prereg clarification" >> hold.log; sleep 60; done'
a=subprocess.Popen(['bash','-lc',s],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('HOLD_PID',a.pid)
