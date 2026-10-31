import subprocess
p=subprocess.Popen(['python3','/content/run_linear.py'],stdout=open('/content/linear_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('PID',p.pid)
