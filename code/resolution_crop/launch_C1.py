from pathlib import Path
import subprocess
p=subprocess.Popen(['python3','/content/remote_crop.py','C1'],stdin=subprocess.DEVNULL,stdout=open('/content/crop_C1_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('PID',p.pid)
