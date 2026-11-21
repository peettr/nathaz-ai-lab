from pathlib import Path
import hashlib,subprocess,time
r=Path('/content/luw-c38-bg1h-v4-20261115_1050')
ps=subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True)
processes=[line.strip() for line in ps.stdout.splitlines() if '/content/remote_BG.py' in line and 'grep ' not in line]
started=(r/'started').exists() or (r/'run.log').exists() or bool(processes)
print('STARTED',started,'PROCESSES',processes,'STATUS',time.time(),'done',(r/'run.done').exists(),'failed',(r/'run.failed').exists(),'result',(r/'result.zip').stat().st_size if (r/'result.zip').exists() else None,flush=True)
for name in ('run.log','solver.log','wrapper.log'):
 p=r/name
 if p.exists():
  with p.open('rb') as f:
   f.seek(max(0,p.stat().st_size-1500));tail=f.read().decode('utf-8','replace')[-900:]
  print(name,'size',p.stat().st_size,'tail',tail,flush=True)
if (r/'run.failed').exists(): print('ERROR',(r/'run.failed').read_text(errors='replace')[-1800:],flush=True)
if (r/'run.done').exists():
 h=hashlib.sha256()
 with (r/'result.zip').open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 print('RESULT_SHA256',h.hexdigest(),flush=True)
