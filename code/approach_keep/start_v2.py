import subprocess
p=subprocess.Popen(['python3','/content/remote_keep.py','E1Wv2'],stdin=subprocess.DEVNULL,stdout=open('/content/E1Wv2_launch.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('E1Wv2',p.pid)
