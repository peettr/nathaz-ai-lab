import pathlib, subprocess
p=pathlib.Path('/content/try9_start.marker')
with p.open('x') as f:
    x=subprocess.Popen(['python3','-u','/content/try9_launch.py'],stdout=open('/content/try9_run.log','x'),stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
    f.write(str(x.pid)+'\n')
print('LAUNCHED',x.pid,flush=True)
