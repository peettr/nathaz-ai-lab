import subprocess, pathlib, os
log=open('/content/s0_pair_1016.log','a',buffering=1)
p=subprocess.Popen(['python','-u','/content/s0_pair_network_1016.py'],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True,cwd='/content')
pathlib.Path('/content/s0_pair_1016.pid').write_text(str(p.pid))
print('STARTED_PID',p.pid)
