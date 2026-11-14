"""Short Colab kernel call to launch detached S2 installer/pilot."""
import pathlib, subprocess, sys
r=pathlib.Path('/content/s2');r.mkdir(exist_ok=True)
f=(r/'pilot.log').open('a',buffering=1)
p=subprocess.Popen([sys.executable,'/content/s2_install_and_pilot_1021.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('PILOT_PID',p.pid,flush=True)
