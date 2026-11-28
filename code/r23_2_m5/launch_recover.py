import subprocess
from pathlib import Path
p=Path('/content/m5')
assert p.exists() and len(list((p/'train_gfs').glob('*.csv')))==374
subprocess.run(['cp','/content/m5/recover_train.sh','/content/m5/recover_train.sh'],check=False) if False else None
f=p/'recover_train.done'
if f.exists(): raise RuntimeError('already started')
proc=subprocess.Popen(['nohup','bash','/content/m5/recover_train.sh'],stdin=subprocess.DEVNULL,stdout=(p/'recover_train.launch').open('w'),stderr=subprocess.STDOUT,start_new_session=True)
print('RECOVERY_PID',proc.pid)
