import subprocess
p=subprocess.Popen(['python3','/content/remote_keep.py','E1W'],stdin=subprocess.DEVNULL,stdout=open('/content/E1W_launch.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('E1W',p.pid)
