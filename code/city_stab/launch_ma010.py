import time,subprocess,pathlib
pathlib.Path('/content/ma010_deadline_epoch.txt').write_text(str(time.time()+1400))
f=open('/content/ma010_launcher.log','w')
p=subprocess.Popen(['python3','/content/run_ma010_remote.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('launched',p.pid,flush=True)
