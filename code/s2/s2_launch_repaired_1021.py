"""Resume S2 pilot after pre-inference coordinate error."""
import os,pathlib,subprocess,sys
r=pathlib.Path('/content/s2');f=(r/'first20.log').open('a',buffering=1)
env=os.environ.copy();env['S2_GROUP_LIMIT']='20'
p=subprocess.Popen([sys.executable,'/content/s2_worker_1021.py'],env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('REPAIRED_PILOT_PID',p.pid,flush=True)
