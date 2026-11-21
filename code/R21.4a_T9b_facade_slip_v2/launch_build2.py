import pathlib,subprocess,sys,os,time
p=pathlib.Path('/content/.t9b2_launched')
if p.exists():print('ALREADY_LAUNCHED',p.read_text());sys.exit(0)
with p.open('x') as f:f.write(str(time.time()))
log=open('/content/t9b2.log','x')
q=subprocess.Popen(['/usr/bin/python3','-u','/content/worker_build2.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=os.environ.copy())
print('LAUNCHED',q.pid,flush=True)
