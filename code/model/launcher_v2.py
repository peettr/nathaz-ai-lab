"""Launch exactly one Colab stage as a detached process, with durable exit marker."""
import os, pathlib, subprocess, sys, time
root=pathlib.Path('/content/l26_19_wp');root.mkdir(exist_ok=True)
name=os.environ['STAGE'];assert name in {'prepare_v2','sample_audit','pilot'}
script=root/(name+'.py');assert script.is_file()
lock=root/(name+'.started')
fd=os.open(str(lock),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
try:
    log=open(root/(name+'.log'),'x')
    worker=subprocess.Popen([sys.executable,'-u',str(script)],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True,cwd=str(root),env={**os.environ,'ATTN_IMPL':'sdpa','HF_HUB_DISABLE_XET':'1'})
    os.write(fd,f'{worker.pid} {time.time()}\n'.encode())
    print('STARTED',name,worker.pid,script,flush=True)
finally: os.close(fd)
