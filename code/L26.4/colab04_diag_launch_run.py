import pathlib,subprocess,os
p=pathlib.Path('/content/l264diag04');p.mkdir(exist_ok=True)
with (p/'diag_run.log').open('x') as log:
    x=subprocess.Popen(['python','/content/colab04_diag_run.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('DIAG_PID',x.pid,flush=True)
