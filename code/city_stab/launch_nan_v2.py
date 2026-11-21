import subprocess
p=subprocess.Popen(['python3','/content/run_nan_v2_remote.py'],stdin=subprocess.DEVNULL,stdout=open('/content/luw_nan_v2_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('PID',p.pid,flush=True)
