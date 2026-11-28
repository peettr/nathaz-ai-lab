import pathlib,subprocess,os,sys,time
p=pathlib.Path('/content/.phaseab_launched')
if p.exists():print('ALREADY_LAUNCHED',p.read_text());sys.exit(0)
fd=os.open(str(p),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:f.write(str(time.time()))
log=open('/content/phaseab.log','x')
q=subprocess.Popen(['/usr/bin/python3','-u','/content/worker.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=os.environ.copy())
print('LAUNCHED',q.pid,flush=True)
