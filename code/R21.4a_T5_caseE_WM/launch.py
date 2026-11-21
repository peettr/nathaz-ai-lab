import pathlib,subprocess,os,sys,time
p=pathlib.Path('/content/.t5_launched')
if p.exists():
 print('ALREADY_LAUNCHED',p.read_text());sys.exit(0)
with p.open('x') as f:f.write(str(time.time()))
log=open('/content/t5.log','x')
q=subprocess.Popen(['/usr/bin/python3','-u','/content/worker.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=os.environ.copy())
print('LAUNCHED',q.pid,flush=True)
