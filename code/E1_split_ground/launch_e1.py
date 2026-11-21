import subprocess
from pathlib import Path
lock=Path('/content/e1_launched')
assert not lock.exists(), 'E1 already launched'
lock.write_text('launched\n')
f=open('/content/E1_driver.log','w')
p=subprocess.Popen(['python3','/content/remote_e1.py'],stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('PID',p.pid)
