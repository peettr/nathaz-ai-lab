import subprocess,sys,pathlib,os
p=pathlib.Path('/content/l264surface07')
with (p/'resume.log').open('w') as f:
 r=subprocess.Popen([sys.executable,'/content/l264resume07.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('RESUME_PID',r.pid,flush=True)
