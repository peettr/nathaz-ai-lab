import os,sys,subprocess,pathlib
p=pathlib.Path('/content/l264a100')
assert (p/'stage.done').is_file() and (p/'install_py310.done').is_file(),'prerequisites not done'
fd=os.open(p/'pilot.started',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:f.write('pilot.py\n')
with open(p/'pilot.log','w') as log:proc=subprocess.Popen([str(p/'venv/bin/python'),'/content/pilot_l264.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('PILOT_PID',proc.pid,flush=True)
