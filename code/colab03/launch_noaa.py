import pathlib,os,subprocess
p=pathlib.Path('/content/l264a100/texas');f=p/'noaa_fetch.started';fd=os.open(f,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
log=(p/'noaa_fetch.log').open('x');x=subprocess.Popen(['/content/l264a100/venv/bin/python','/content/fetch_noaa_l264_v2.py','--start','0','--count','720','--workers','8'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('NOAA_FETCH_PID',x.pid,flush=True)
