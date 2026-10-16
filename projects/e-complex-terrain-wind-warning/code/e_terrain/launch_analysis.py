import os,subprocess,sys
from pathlib import Path
r=Path('/content/e_terrain');lock=r/'analysis_launch.lock'
with lock.open('x') as f:f.write('53a160da')
log=(r/'analysis.log').open('x')
p=subprocess.Popen([sys.executable,str(r/'analyze_and_windninja.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(r/'analysis_pid').write_text(str(p.pid))
print('ANALYSIS_LAUNCHED',p.pid,flush=True)
