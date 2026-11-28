import subprocess
p=subprocess.Popen(['python3','/content/remote_keep.py','E1Wv4'],stdin=subprocess.DEVNULL,stdout=open('/content/E1Wv4_launch.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('E1Wv4',p.pid)
