import os,sys,subprocess,pathlib
p=pathlib.Path('/content/l264a100');assert p.joinpath('stage.failed').exists()
fd=os.open(p/'stage_resume.started',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:f.write('stage_resume.py\n')
with (p/'stage_resume.log').open('w') as log:
 proc=subprocess.Popen([sys.executable,'/content/stage_resume_l264.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('STAGE_RESUME_PID',proc.pid,flush=True)
