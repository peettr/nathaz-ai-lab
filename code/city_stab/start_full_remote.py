import subprocess
p=subprocess.Popen(['python3','/content/run_full_remote.py'],stdin=subprocess.DEVNULL,stdout=open('/content/city_full_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('CITY_FULL_PID',p.pid,flush=True)
