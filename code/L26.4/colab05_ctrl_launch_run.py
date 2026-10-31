import pathlib,subprocess
p=pathlib.Path('/content/l264ctrl05');p.mkdir(exist_ok=True)
with (p/'ctrl_run.log').open('x') as f:
 x=subprocess.Popen(['python','/content/colab05_ctrl_run.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('CTRL_PID',x.pid,flush=True)
