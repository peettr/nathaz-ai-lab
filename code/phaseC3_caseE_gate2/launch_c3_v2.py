import subprocess
p=subprocess.Popen(['python3','/content/run_c3_v2_remote.py'],stdin=subprocess.DEVNULL,stdout=open('/content/luw_c3_v2_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('C3_V2_PID',p.pid,flush=True)
