import subprocess
p=subprocess.Popen(['python3','/content/run_precision_full.py'],stdout=open('/content/full.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('FULL_LAUNCHED',p.pid)
