import pathlib,subprocess,os,time
p=pathlib.Path('/content/.t8_launched')
if p.exists():print('ALREADY_LAUNCHED',p.read_text())
else:
 with p.open('x') as f:f.write(str(time.time()))
 log=open('/content/t8.log','x')
 q=subprocess.Popen(['/usr/bin/python3','-u','/content/worker.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=os.environ.copy())
 print('LAUNCHED',q.pid,flush=True)
