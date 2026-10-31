import pathlib,subprocess,os
p=pathlib.Path('/content/l264a100/texas')
with (p/'west_batch_v4.log').open('x') as log:
 proc=subprocess.Popen(['/content/l264a100/venv/bin/python','/content/l264_west_forecasts_v3.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env={**os.environ,'MPLBACKEND':'Agg'})
print('WEST_V4_PID',proc.pid,flush=True)
