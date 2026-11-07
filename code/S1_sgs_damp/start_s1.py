import subprocess
p=subprocess.Popen(['python3','/content/remote_s1.py'],stdin=subprocess.DEVNULL,stdout=open('/content/s1_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print(p.pid)
