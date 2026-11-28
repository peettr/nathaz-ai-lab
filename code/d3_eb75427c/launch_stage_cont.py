import os, pathlib, subprocess
r=pathlib.Path('/content/l2631'); r.mkdir(exist_ok=True)
lock=r/'stage_cont.started'
with lock.open('x') as f: f.write('started')
log=(r/'stage_cont.log').open('x')
subprocess.Popen(['python','-u',str(r/'stage_weatherbench.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('STAGE_STARTED')
