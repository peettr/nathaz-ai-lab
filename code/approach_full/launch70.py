import subprocess
f=open('/content/FG0A70.launch','w',buffering=1)
p=subprocess.Popen(['python3','/content/remote_full.py','FG0A70'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print(p.pid)
