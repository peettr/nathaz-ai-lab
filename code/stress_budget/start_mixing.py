import subprocess
p=subprocess.Popen(['python3','/content/run_mixing.py'],stdout=open('/content/mixing.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('MIXING_LAUNCHED',p.pid)
