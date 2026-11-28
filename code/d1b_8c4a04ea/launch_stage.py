import os, subprocess, pathlib
root=pathlib.Path('/content/l2631');root.mkdir(exist_ok=True)
log=open(root/'stage_v3.log','xb')
subprocess.Popen(['python','-u',str(root/'stage_weatherbench.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('STAGE_STARTED')
