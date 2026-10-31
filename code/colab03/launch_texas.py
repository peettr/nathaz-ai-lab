import pathlib,subprocess,os
p=pathlib.Path('/content/l264a100/texas');fd=os.open(p/'texas_batch.started',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
with (p/'texas_batch.log').open('x') as log:
 proc=subprocess.Popen(['/content/l264a100/venv/bin/python','/content/l264_texas_forecasts.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('TEXAS_BATCH_PID',proc.pid,flush=True)
