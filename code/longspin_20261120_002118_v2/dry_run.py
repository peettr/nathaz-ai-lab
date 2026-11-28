#!/usr/bin/env python3
"""Execute the real worker in PAYLOAD-only /content, stub solver only."""
import pathlib,shutil,json,time,threading,subprocess,sys,hashlib
R=pathlib.Path(__file__).resolve().parent;C=R/'dry_content';C.mkdir(exist_ok=False)
files=['worker_longspin.py','analyze_longspin.py','longspin_stage.tar.gz','longspin_manifest.json','stub_longspin.py']
for n in files:shutil.copyfile(R/n,C/n)
(C/'longspin_budget.json').write_text(json.dumps({'mode':'longspin','fixture':True,'work_deadline':time.time()+600,'teardown_s':30})+'\n')
expected=set(files+['longspin_budget.json']);assert {x.name for x in C.iterdir()}==expected
hashes={}
def send_ack():
 global hashes
 limit=time.monotonic()+450
 while time.monotonic()<limit:
  p=C/'longspin/out/handoff.json'
  if p.is_file():
   hashes=json.loads(p.read_text())['sha256']
   for n,h in hashes.items():
    x=p.parent/n
    if not x.is_file() or hashlib.sha256(x.read_bytes()).hexdigest()!=h or x.with_name(x.name+'.sha256').read_text().strip()!=h:raise RuntimeError('handoff mismatch '+n)
   (p.parent/'handoff.ack.json').write_text(json.dumps(hashes)+'\n');return
  time.sleep(.1)
 raise TimeoutError('no handoff')
t=threading.Thread(target=send_ack,daemon=True);t.start()
p=subprocess.run([sys.executable,str(C/'worker_longspin.py')],cwd=C,env={**__import__('os').environ,'T17_CONTENT':str(C)},capture_output=True,text=True,timeout=530)
(R/'DRY_WORKER.log').write_text(p.stdout+'\nSTDERR:\n'+p.stderr+'\nEXIT '+str(p.returncode)+'\n')
t.join(3)
assert p.returncode==0,(p.stderr[-1000:],p.stdout[-1000:])
assert len(hashes)==19 and (C/'longspin/out/run.done').is_file(),(len(hashes),p.stdout[-500:])
assert len([x for x in (C/'longspin/out').glob('window_*.json')])==15
(R/'PREFLIGHT_LONGSPIN.ok').write_text(json.dumps({n:hashlib.sha256((R/n).read_bytes()).hexdigest() for n in files if n!='stub_longspin.py'}|{'controller_longspin.py':hashlib.sha256((R/'controller_longspin.py').read_bytes()).hexdigest(),'remote_longspin.py':hashlib.sha256((R/'remote_longspin.py').read_bytes()).hexdigest()},indent=2)+'\n')
print('DRY_PASS 15 windows, 19 files, SHA ACK; solver stub only')
