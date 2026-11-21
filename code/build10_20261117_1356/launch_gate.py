import pathlib,subprocess,os
p=pathlib.Path('/content/t9b10.launch');
try:
 fd=os.open(str(p),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o644)
except FileExistsError:
 print('ALREADY_LAUNCHED',p.read_text(),flush=True)
else:
 f=open('/content/t9b10.log','x');q=subprocess.Popen(['python3','/content/worker_gate.py'],cwd='/content',stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 os.write(fd,str(q.pid).encode());os.close(fd);print('LAUNCHED',q.pid,flush=True)
