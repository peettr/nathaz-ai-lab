import subprocess,os
p=subprocess.Popen(['python3','/content/remote_B2s.py'],stdin=subprocess.DEVNULL,stdout=open('/content/b2s_launcher.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('B2S_PID',p.pid)
