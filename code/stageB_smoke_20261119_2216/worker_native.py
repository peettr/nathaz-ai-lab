#!/usr/bin/env python3
"""T17-B continuous six-case worker; one solver process per case, no restart at V0."""
import csv, hashlib, json, os, pathlib, shutil, subprocess, tarfile, time, traceback
from native_analysis import decide,summarize
from assert_T17 import evaluate,seed_metrics
GROUPS=('bounce','t4','t15');SEEDS=('1','2')
C=pathlib.Path(os.environ.get('T17_CONTENT','/content'));ROOT=C/'t17b';OUT=ROOT/'out'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def seal(p):
 (p.parent/(p.name+'.sha256')).write_text(sha(p)+'\n')
 print('READY',p.name,sha(p),flush=True)
def run(c=C):
 global C,ROOT,OUT
 C=c;ROOT=c/'t17b';OUT=ROOT/'out'
 budget=json.loads((c/'t17b_budget.json').read_text())
 mode=budget['mode'];deadline=budget['work_deadline']
 spec=json.loads((c/'t17b_manifest.json').read_text())
 arc=c/'t17b_stage.tar.gz'
 if sha(arc)!=spec['archive_sha256']:raise ValueError('archive hash mismatch')
 ROOT.mkdir(exist_ok=False);OUT.mkdir()
 try:
  with tarfile.open(arc) as t:
   for m in t:
    p=pathlib.PurePosixPath(m.name)
    if not p.parts or p.parts[0]!='pack_stage' or '..' in p.parts or not(m.isdir() or m.isfile()):raise ValueError('unsafe tar member')
   t.extractall(ROOT,filter='data')
  exes={}
  for group in (('t15',) if mode=='smoke' else GROUPS):
   src=ROOT/'pack_stage'/spec['variant_names'][group]
   for name,h in spec['variants'][spec['variant_names'][group]].items():
    if sha(src/'src'/name)!=h:raise ValueError('source hash mismatch '+name)
   logfile=OUT/(group+'_gpu_compile.log')
   with logfile.open('x') as out: rc=subprocess.run(['make','Linux','-j8'],cwd=src,stdout=out,stderr=subprocess.STDOUT,timeout=500).returncode
   seal(logfile)
   if rc:raise RuntimeError('native build failed '+group)
   exe=src/'bin/FluidX3D'
   if budget.get('fixture'):
    shutil.copyfile(c/'stub_native.py',exe);exe.chmod(0o755)
   exes[group]=(exe,src)
  cases={g:{} for g in GROUPS}
  order=(('t15','1'),) if mode=='smoke' else tuple((g,s) for g in GROUPS for s in SEEDS)
  for idx,(group,seed) in enumerate(order):
   label=group+'_s'+seed;exe,src=exes[group]
   # Full remaining-chain upper runtime including all possible 3T V0 extensions.
   remain=order[idx:]
   worst=sum(((2800 if mode=='smoke' else 10*budget['steps_per_T'])/budget['steps_per_second'][g]+budget['per_case_overhead_s']) for g,s in remain)
   margin=deadline-time.time()-worst-budget['teardown_s']
   print('BUDGET_MARGIN',label,margin,flush=True)
   if margin<=0:raise TimeoutError('next case cannot fit in CU budget')
   d=OUT/label;d.mkdir()
   env={**os.environ,'T17_B_MODE':mode,'T17_B_DIR':str(d),'T17_B_SEED':seed,
        'T17_STAGE_A_ALLOW':'1','LD_LIBRARY_PATH':str(src/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
   log=OUT/(label+'_solver.log')
   with log.open('x') as f:
    proc=subprocess.Popen([str(exe)],cwd=src,env=env,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
    attempts=0;decision_seen=set()
    while proc.poll() is None:
     if time.time()>=deadline-budget['teardown_s']:
      proc.terminate();raise TimeoutError('solver deadline '+label)
     for a in range(4):
      ready=d/(f'v0_{a}.ready')
      if ready.exists() and a not in decision_seen:
       end=int(ready.read_text().strip())
       half=200 if mode=='smoke' else round(budget['steps_per_T']/2)
       pair,choice=decide(d,a,end,half,mode=='smoke')
       decision_seen.add(a);print('V0_DECISION',label,a,choice,pair,flush=True)
     time.sleep(.1 if mode=='fixture' else 1)
    if proc.returncode:seal(log);raise RuntimeError('solver failed '+label+' rc='+str(proc.returncode))
   seal(log)
   if not (d/'producer.done').exists():raise RuntimeError('missing producer.done '+label)
   if mode=='smoke':
    # Shortened four-block window: only verifies real readback, binary planes,
    # contract and frozen assert function consume finite values. No §3 verdict.
    table=list(csv.DictReader((d/'profiles.csv').open()))
    timing=list(csv.DictReader((d/'timing.csv').open()))
    n=(d/'planes.bin').stat().st_size
    if not table or not timing or n<=0 or n%(2*256*128*3*4):raise RuntimeError('smoke producer incomplete')
    result=summarize(d)
    checks=seed_metrics(result)
    cloned={'schema':'T17-B-v1','cases':{g:{s:result for s in SEEDS} for g in GROUPS}}
    pipeline=evaluate(cloned)
    def finite_tree(obj):
     if isinstance(obj,float):return __import__('math').isfinite(obj)
     if isinstance(obj,dict):return all(finite_tree(v) for v in obj.values())
     if isinstance(obj,list):return all(finite_tree(v) for v in obj)
     return True
    if not finite_tree(result) or not finite_tree(pipeline):raise RuntimeError('nonfinite contract/assert output')
    if not all(__import__('math').isfinite(float(r['u_x_mean_si'])) for r in table):raise RuntimeError('smoke nonfinite')
    output={'schema':'T17-B-smoke','profile_rows':len(table),'plane_bytes':n,
            'v0_rows':len(timing),'finite':True,'contract':result,
            'assert_T17_seed_metrics':checks,'assert_T17_cloned_pipeline':pipeline,'science_verdict':'not_evaluated_short_window'}
    x=OUT/'smoke_pipeline.json';x.write_text(json.dumps(output,allow_nan=False)+'\n');seal(x)
   else:
    result=summarize(d)
    seed_metrics(result)
    x=OUT/(label+'_case.json');x.write_text(json.dumps(result)+'\n');seal(x)
    cases[group][seed]=result
   # Compact evidence only: plane binaries remain on VM; seal their hashes in summary.
   local_files=[p for p in d.iterdir() if p.is_file() and p.suffix in ('.csv','.txt','.ready','.decision','.done')]
   files=[]
   for source in local_files:
    target=OUT/(label+'_'+source.name)
    shutil.copyfile(source,target);seal(target);files.append(target)
   files.extend((log,x))
   hashes={p.name:sha(p) for p in files}
   manifest=OUT/(label+'_handoff.json');manifest.write_text(json.dumps({'sha256':hashes})+'\n');seal(manifest)
   ack=OUT/(label+'.ack.json')
   while not ack.exists():
    if time.time()>=deadline-budget['teardown_s']:raise TimeoutError('missing ACK '+label)
    time.sleep(.1 if mode=='fixture' else 2)
   if json.loads(ack.read_text())!=hashes:raise RuntimeError('ACK mismatch '+label)
   print('HOST_VERIFIED',label,flush=True)
  if mode=='production':
   data={'schema':'T17-B-v1','cases':cases};result=evaluate(data)
   x=OUT/'T17_result.json';x.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');seal(x)
  done=OUT/'run.done';done.write_text(json.dumps({'verified':[g+'_s'+s for g,s in order]})+'\n');seal(done)
 except BaseException:
  x=OUT/'run.failed';x.write_text(traceback.format_exc());seal(x);raise

def fixture_decision(d,a,end,half):
 # Fixture solver may produce a handoff without the native 5T history.
 (d/f'v0_{a}.decision').write_text('pass\n')
 return [],'pass'
if __name__=='__main__':run()
