import subprocess
p=subprocess.Popen(['python3','/content/run_city_noT_remote.py'],stdin=subprocess.DEVNULL,stdout=open('/content/luw_city_noT_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('CITY_NOT_PID',p.pid,flush=True)
