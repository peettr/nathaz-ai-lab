import subprocess
p=subprocess.Popen(['python3','/content/run_full_remote_v3.py'],stdin=subprocess.DEVNULL,stdout=open('/content/city_full_driver_v3.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('CITY_FULL_V3_PID',p.pid,flush=True)
