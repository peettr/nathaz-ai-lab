import pathlib,os,subprocess
p=pathlib.Path('/content/l264a100/texas');f=p/'pilot03.started'
fd=os.open(f,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
with (p/'pilot03.log').open('x') as log:
 proc=subprocess.Popen(['/content/l264a100/venv/bin/python','/content/l264_forecast_v2.py','--net','surface','--region','texas','--variant','texas','--days','1'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('PILOT_PID',proc.pid,flush=True)
