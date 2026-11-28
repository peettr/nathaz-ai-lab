import os,subprocess,pathlib
p=pathlib.Path('/content/try11_noshear_v2.launch.lock')
fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:f.write('started\n')
out=open('/content/try11_noshear_v2_launcher.log','x')
process=subprocess.Popen(['python3','/content/launch_noshear_v2.py'],stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
out.close();print('LAUNCHED_PID',process.pid,flush=True)
