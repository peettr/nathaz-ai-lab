#!/usr/bin/env python3
"""T17 A1b C1/C2 isolated worker; only solver may be stubbed."""
import argparse,csv,hashlib,json,os,pathlib,shutil,subprocess,tarfile,time,traceback
C=pathlib.Path('/content');LABELS=('d1','d2')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def seal(p):
 (p.parent/(p.name+'.sha256')).write_text(sha(p)+'\n');print('READY',p.name,sha(p),flush=True)
def run(c,stub=None):
 budget=json.loads((c/'diag_budget.json').read_text());deadline=budget['work_deadline'];fixture=budget['mode']=='fixture'
 assert fixture==bool(stub)
 man=json.loads((c/'diag_manifest.json').read_text());arc=c/'diag_stage.tar.gz'
 assert sha(arc)==man['archive_sha256']
 out=c/'diag/out';out.mkdir(parents=True,exist_ok=False)
 try:
  with tarfile.open(arc) as t:
   for m in t:
    p=pathlib.PurePosixPath(m.name)
    if not p.parts or p.parts[0]!='stage' or '..' in p.parts or not(m.isdir() or m.isfile()):raise ValueError('unsafe tar')
   t.extractall(c/'diag',filter='data')
  src=c/'diag/stage'
  for n,h in man['source_sha256'].items():assert sha(src/'src'/n)==h,(n,h)
  log=out/'build.log'
  with log.open('x') as f:rc=subprocess.run(['make','Linux','-j8'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=120).returncode
  seal(log)
  if rc:raise RuntimeError('build failed')
  exe=src/'bin/FluidX3D';assert exe.is_file()
  if stub:shutil.copyfile(stub,exe);exe.chmod(0o755)
  cl=out/'gpu_compile.log'
  env={**os.environ,'T17_STAGE_A_ALLOW':'1','LUW_COMPILE_ONLY':'1','LD_LIBRARY_PATH':str(src/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
  with cl.open('x') as f:rc=subprocess.run([str(exe)],cwd=src,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=120).returncode
  seal(cl)
  if rc or (not fixture and 'COMPILE_ONLY PASS' not in cl.read_text(errors='replace')):raise RuntimeError('compile fail')
  for label in LABELS:
   # Remaining solver cases + per-case host evidence/ACK + final transfer.
   margin=deadline-time.time()-(65 if label=='d1' else 0)-65-35
   print('BUDGET_STAGE',label,'margin_s',round(margin,3),flush=True)
   if margin<=0:raise TimeoutError('no time '+label)
   ledger=out/(label+'_ledger.csv');sol=out/(label+'_solver.log')
   env2={**env,'T17_A1B_MIRROR_UNFORCED':'1','T17_A1B_DIAG':'1','T17_A1B_UNIFORM':'1','T17_A1B_ZERO':'1' if label=='d2' else '0','T17_LAYER_CSV':str(out/(label+'_layers.csv')), 'T17_DIAGNOSTIC_STEPS':'1000','T17_LEDGER_CSV':str(ledger)}
   env2.pop('LUW_COMPILE_ONLY',None)
   with sol.open('x') as f:rc=subprocess.run([str(exe)],cwd=src,env=env2,stdout=f,stderr=subprocess.STDOUT,timeout=min(65,max(1,deadline-time.time()-35))).returncode
   seal(sol)
   if ledger.is_file():seal(ledger)
   layers=out/(label+'_layers.csv')
   if layers.is_file():seal(layers)
   if rc or not ledger.is_file() or not layers.is_file():raise RuntimeError('solver '+label+' failed '+str(rc))
   with ledger.open() as f:rows=list(csv.DictReader(f))
   steps=[int(r['step']) for r in rows]
   assert steps==list(range(101))+list(range(110,1001,10)),(len(steps),steps[-5:])
   with layers.open() as f: layer_rows=list(csv.DictReader(f))
   assert len(layer_rows)==64*len(rows) and {(int(r['step']),int(r['z'])) for r in layer_rows}=={(step,z) for step in steps for z in range(1,65)}
   files=[ledger,layers,sol]
   if label=='d1':files.append(cl)
   hashes={p.name:sha(p) for p in files};hand=out/(label+'_handoff.json');hand.write_text(json.dumps({'sha256':hashes})+'\n');seal(hand)
   ack=out/(label+'.ack.json')
   while not ack.exists():
    if time.time()+5>deadline:raise TimeoutError('ACK '+label)
    time.sleep(.2 if fixture else 2)
   if json.loads(ack.read_text())!=hashes:raise RuntimeError('ACK mismatch')
   print('HOST_VERIFIED',label,flush=True)
  done=out/'run.done';done.write_text(json.dumps({'verified_cases':list(LABELS)})+'\n');seal(done)
 except BaseException:
  p=out/'run.failed';p.write_text(traceback.format_exc());seal(p);raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--content',type=pathlib.Path,default=C);p.add_argument('--stub',type=pathlib.Path);a=p.parse_args();run(a.content.resolve(),a.stub.resolve() if a.stub else None)
