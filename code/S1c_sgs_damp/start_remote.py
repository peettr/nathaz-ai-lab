import subprocess
p=subprocess.Popen(['python3','/content/remote_s1c.py'],stdin=subprocess.DEVNULL,stdout=open('/content/s1c_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('S1C_PID',p.pid,flush=True)
