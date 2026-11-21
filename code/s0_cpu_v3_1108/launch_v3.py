import os, pathlib, subprocess, sys
r=pathlib.Path('/content/r4_s0'); r.mkdir(exist_ok=True)
marker=r/'launch_v3.claim'
fd=os.open(marker,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
os.write(fd,b'r234b-r4-s0-cpu-v3-1108\n');os.close(fd)
log=open(r/'run_v3.log','w',buffering=1)
code="import subprocess,pathlib; p=subprocess.run(['python3','-u','/content/r4_s0_pair_cpu_v3.py'],stdout=open('/content/r4_s0/run_v3.log','a',buffering=1),stderr=subprocess.STDOUT); pathlib.Path('/content/r4_s0/run_v3.exit').write_text(str(p.returncode))"
p=subprocess.Popen([sys.executable,'-u','-c',code],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('STARTED',p.pid,marker)
