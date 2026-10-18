import subprocess
p=subprocess.Popen(['python3','/content/run_bisect.py'],stdout=open('/content/bisect_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('PID',p.pid)
