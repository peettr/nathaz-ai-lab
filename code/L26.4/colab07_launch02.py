import subprocess,sys,pathlib
p=pathlib.Path('/content/l264surface07')
f=(p/'second_resume.log').open('x')
r=subprocess.Popen([sys.executable,'/content/l264resume02.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('PID',r.pid,flush=True)
