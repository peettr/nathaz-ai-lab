import os,subprocess
fd=os.open('/content/try13_shear.launch.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:f.write('started\n')
with open('/content/try13_shear_launcher.log','x') as out:
    p=subprocess.Popen(['python3','/content/run_shear.py'],stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
print('LAUNCHED_PID',p.pid,flush=True)
