import subprocess
p=subprocess.Popen(['python3','-u','/content/remote_regression.py'],stdout=open('/content/lhigh_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('PID',p.pid)
