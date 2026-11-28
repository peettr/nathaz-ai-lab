import pathlib,subprocess,os
p=pathlib.Path('/content/t9b16.launch');
try:
 fd=os.open(str(p),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o644)
except FileExistsError:
 print('ALREADY_LAUNCHED',p.read_text(),flush=True)
else:
 import hashlib,json
 assert all(hashlib.sha256(pathlib.Path('/content',n).read_bytes()).hexdigest()==h for n,h in json.loads(pathlib.Path('/content/t9b16_upload.json').read_text()).items())
 os.environ.pop('T9B_PREFLIGHT_SOLVER',None)
 f=open('/content/t9b16.log','x');q=subprocess.Popen(['python3','/content/worker_gate.py'],cwd='/content',stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 os.write(fd,str(q.pid).encode());os.close(fd);print('LAUNCHED',q.pid,flush=True)
