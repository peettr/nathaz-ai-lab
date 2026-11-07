import subprocess
f=open('/content/ma010_v2_launcher.log','w')
p=subprocess.Popen(['python3','/content/run_ma010_v2_remote.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('launched',p.pid,flush=True)
