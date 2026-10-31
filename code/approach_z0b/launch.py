import subprocess,os
p='/content/luw_z0b.launch'
assert not os.path.exists(p)
f=open(p,'w',buffering=1)
r=subprocess.Popen(['python3','/content/remote_z0b.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print(r.pid)
