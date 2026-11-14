from pathlib import Path
import subprocess,sys
T='FGz2c'
R=Path('/content/luw_sponge_'+T)
assert not R.exists(),str(R)
with open('/content/precorr.launch','w',buffering=1) as f:
 p=subprocess.Popen(['python3','/content/remote_sponge.py',T],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('LAUNCHED',p.pid,flush=True)
