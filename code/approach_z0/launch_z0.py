import subprocess
f=open('/content/luw_z0.launch','w',buffering=1)
p=subprocess.Popen(['python3','/content/remote_z0.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print(p.pid)
