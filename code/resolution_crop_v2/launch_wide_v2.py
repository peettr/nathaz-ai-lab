import subprocess
p=subprocess.Popen(['python3','/content/remote_v2.py','C1widev2'],stdout=open('/content/cropv2wide_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('PID',p.pid)
