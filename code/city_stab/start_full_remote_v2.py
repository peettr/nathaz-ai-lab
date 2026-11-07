import subprocess
p=subprocess.Popen(['python3','/content/run_full_remote_v2.py'],stdin=subprocess.DEVNULL,stdout=open('/content/city_full_driver_v2.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('CITY_FULL_V2_PID',p.pid,flush=True)
