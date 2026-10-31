import subprocess,os
os.makedirs('/content/m4',exist_ok=True)
log=open('/content/m4/train.log','ab',buffering=0)
cmd='python /content/m4_training.py obs && python /content/m4_training.py gfs && python /content/m4_training.py fit; rc=$?; printf "%s\\n" "$rc" > /content/m4/train.exit; touch /content/m4/train.done'
p=subprocess.Popen(['bash','-c',cmd],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,cwd='/content')
print('TRAIN_PID',p.pid,'COMMAND',cmd)
