#!/usr/bin/env python3
"""One continuous 30T T15 s1 diagnostic; only solver binary is stubbed in dry run."""
import hashlib,json,os,pathlib,shutil,subprocess,tarfile,time,traceback
from analyze_longspin import analyze
C=pathlib.Path(os.getenv('T17_CONTENT','/content'));ROOT=C/'longspin';OUT=ROOT/'out'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def seal(p):
 (p.parent/(p.name+'.sha256')).write_text(sha(p)+'\n');print('READY',p.name,sha(p),flush=True)
def run(c=C):
 global C,ROOT,OUT
 C=c;ROOT=c/'longspin';OUT=ROOT/'out';budget=json.loads((C/'longspin_budget.json').read_text());deadline=budget['work_deadline']
 spec=json.loads((C/'longspin_manifest.json').read_text());arc=C/'longspin_stage.tar.gz'
 if sha(arc)!=spec['archive_sha256']:raise ValueError('archive mismatch')
 ROOT.mkdir(exist_ok=False);OUT.mkdir()
 try:
  with tarfile.open(arc) as t:
   for m in t:
    p=pathlib.PurePosixPath(m.name)
    if not p.parts or p.parts[0]!='pack_stage' or '..' in p.parts or not (m.isdir() or m.isfile()):raise ValueError('unsafe member')
   t.extractall(ROOT,filter='data')
  src=ROOT/'pack_stage/periodic_t15_k2'
  for n,h in spec['source_files'].items():
   if sha(src/'src'/n)!=h:raise ValueError('source mismatch '+n)
  log=OUT/'native_compile.log'
  with log.open('x') as f:rc=subprocess.run(['make','Linux','-j8'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=500).returncode
  seal(log)
  if rc:raise RuntimeError('compile failed')
  exe=src/'bin/FluidX3D'
  if budget.get('fixture'):
   shutil.copyfile(C/'stub_longspin.py',exe);exe.chmod(0o755)
  d=OUT/'case';d.mkdir()
  env={**os.environ,'T17_B_MODE':'production','T17_B_DIR':str(d),'T17_STAGE_A_ALLOW':'1',
       'LD_LIBRARY_PATH':str(src/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
  log=OUT/'solver.log'
  with log.open('x') as f:proc=subprocess.Popen([str(exe)],cwd=src,env=env,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
  delivered=set()
  while proc.poll() is None or len(delivered)<15:
   if time.time()>deadline-budget['teardown_s']:
    if proc.poll() is None:proc.terminate()
    raise TimeoutError('longspin deadline')
   for w in range(1,16):
    marker=d/('window_%d.ready'%w)
    if marker.exists() and w not in delivered:
     # The solver flushes ledger/plane/profile before publishing this marker.
     subprocess.run([__import__('sys').executable,str(C/'analyze_longspin.py'),str(d),str(w)],check=True,timeout=90)
     p=OUT/('window_%02d.json'%w)
     delivered.add(w);print('WINDOW_DONE',w,p.name,flush=True)
   if proc.poll() is not None:
    if proc.returncode:seal(log);raise RuntimeError('solver failed rc='+str(proc.returncode))
    if not (d/'producer.done').exists():raise RuntimeError('missing producer.done')
    if len(delivered)==15:break
   time.sleep(.1 if budget.get('fixture') else 2)
  seal(log)
  for n in ('timing.csv','producer.done'):
   p=d/n;dst=OUT/n;shutil.copyfile(p,dst);seal(dst)
  manifest=OUT/'handoff.json';names=['native_compile.log','solver.log','timing.csv','producer.done']+[f'window_{w:02d}.json' for w in range(1,16)]
  hashes={n:sha(OUT/n) for n in names};manifest.write_text(json.dumps({'sha256':hashes})+'\n');seal(manifest)
  ack=OUT/'handoff.ack.json'
  while not ack.exists():
   if time.time()>deadline-budget['teardown_s']:raise TimeoutError('missing ACK')
   time.sleep(.1 if budget.get('fixture') else 2)
  if json.loads(ack.read_text())!=hashes:raise RuntimeError('ACK mismatch')
  done=OUT/'run.done';done.write_text(json.dumps({'windows':15,'ack':True})+'\n');seal(done)
 except BaseException:
  p=OUT/'run.failed';p.write_text(traceback.format_exc());seal(p);raise
if __name__=='__main__':run()
