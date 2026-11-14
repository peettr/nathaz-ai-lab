import subprocess
p=subprocess.Popen(['python3','/content/remote_crop.py','C1wide'],stdin=subprocess.DEVNULL,stdout=open('/content/crop_C1wide_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('PID',p.pid)
