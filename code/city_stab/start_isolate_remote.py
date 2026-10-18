import subprocess
p=subprocess.Popen(['python3','/content/run_isolate_remote.py'],stdin=subprocess.DEVNULL,stdout=open('/content/luw_iso_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('ISOLATE_PID',p.pid,flush=True)
