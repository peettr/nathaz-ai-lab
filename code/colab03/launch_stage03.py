import pathlib,subprocess,os
p=pathlib.Path('/content/l264texas01');p.mkdir(exist_ok=True)
fd=os.open(p/'stage.started',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
f=(p/'stage.log').open('w')
x=subprocess.Popen(['python','/content/l264_stage_env.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('STAGE_PID',x.pid,flush=True)
