import subprocess,pathlib,os
p=pathlib.Path('/content/l264diag04')
with (p/'diag_recovery.log').open('x') as f:
 q=subprocess.Popen(['python','/content/colab04_diag_recovery.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,env={**os.environ,'MPLBACKEND':'Agg'})
print('RECOVERY_PID',q.pid)
