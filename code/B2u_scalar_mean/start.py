import subprocess,os
p=subprocess.Popen(['python3','/content/remote_B2u.py'],stdout=open('/content/b2u_driver.log','w'),stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True,cwd='/content')
print('PID',p.pid)
