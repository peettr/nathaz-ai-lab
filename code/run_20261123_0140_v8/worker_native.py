#!/usr/bin/env python3
"""T17-B continuous six-case worker; one solver process per case, no restart at V0."""
import csv, hashlib, json, os, pathlib, shutil, subprocess, tarfile, time, traceback
from native_analysis import decide,summarize
from analyze_longspin import analyze
GROUPS=('K1a','K1b','K2','K3a','K3b');SEEDS=('1',)
C=pathlib.Path(os.environ.get('T17_CONTENT','/content'));ROOT=C/'t17b';OUT=ROOT/'out'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def seal(p):
 (p.parent/(p.name+'.sha256')).write_text(sha(p)+'\n')
 print('READY',p.name,sha(p),flush=True)
def validate_contract(r):
 import math
 if set(r)<{'v0_attempts','stress','blocks','correlations','profile_u','native_provenance'}:raise ValueError('contract missing fields')
 if len(r['profile_u'])!=64 or set(r['profile_u'])!={str(k) for k in range(1,65)}:raise ValueError('contract requires 64 levels')
 if len(r['blocks'])!=4 or not r['v0_attempts']:raise ValueError('contract blocks/V0')
 if float(r['stress']['tau_x_time_mean'])<=0:raise ValueError('tau_x must be positive drag')
 def walk(x):
  if isinstance(x,dict):return all(walk(y) for y in x.values())
  if isinstance(x,list):return all(walk(y) for y in x)
  if isinstance(x,(float,int)):return math.isfinite(x)
  return isinstance(x,str)
 if not walk(r):raise ValueError('nonfinite contract')
 return True

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
  for group in ('B0',)+GROUPS:
   src=ROOT/'pack_stage'/spec['variant_names'][group]
   for name,h in spec['variants'][spec['variant_names'][group]].items():
    if sha(src/'src'/name)!=h:raise ValueError('source hash mismatch '+name)
   logfile=OUT/(group+'_gpu_compile.log')
   if budget.get('fixture'):
    rc=0;logfile.write_text('FIXTURE_ONLY: native build skipped; solver binary replaced by synthetic stub\n');seal(logfile)
   else:
    with logfile.open('x') as out: rc=subprocess.run(['make','Linux','-j8'],cwd=src,stdout=out,stderr=subprocess.STDOUT,timeout=500).returncode
    seal(logfile)
   if rc:raise RuntimeError('native build failed '+group)
   exe=src/'bin/FluidX3D'
   if not budget.get('fixture') and exe.read_bytes()[:4]!=b'\x7fELF':
    raise RuntimeError('native executable is not ELF: '+group)
   if budget.get('fixture'):
    exe.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(c/'stub_t18.py',exe);shutil.copyfile(c/'stub_native_original.py',exe.parent/'stub_native_original.py');exe.chmod(0o755)
   exes[group]=(exe,src)
  # C-0 uses the already native-compiled K3a, then applies the frozen rho gate.
  c0=OUT/'C0_K3a';c0.mkdir()
  c0_env={**os.environ,'T17_B_MODE':'smoke','T17_B_DIR':str(c0),
          'T17_B_SEED':'1','T17_STAGE_A_ALLOW':'1',
          'LD_LIBRARY_PATH':str(exes['K3a'][1]/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
  c0_log=OUT/'C0_K3a_solver.log'
  c0_pass=False
  with c0_log.open('x') as out:
   proc=subprocess.Popen([str(exes['K3a'][0])],cwd=exes['K3a'][1],env=c0_env,
                         stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT)
   while proc.poll() is None:
    if time.time()>=deadline-budget['teardown_s']:
     proc.terminate();raise TimeoutError('C0 deadline')
    time.sleep(.1 if budget.get('fixture') else 2)
   c0_pass=(proc.returncode==0 and (c0/'producer.done').is_file())
  seal(c0_log)
  monitor=c0/'rho_monitor.csv'
  if not budget.get('fixture') and c0_pass:
   import math
   lines=monitor.read_text().splitlines() if monitor.exists() else []
   expected=list(range(1000,53001,1000))+[53851]
   rows=[line.split(',') for line in lines]
   c0_pass=(len(rows)==len(expected) and [int(x[0]) for x in rows]==expected
     and all(len(x)==3 and all(math.isfinite(float(y)) for y in x[1:])
        and .9<=float(x[1])<=float(x[2])<=1.1 for x in rows))
  rows=[] if budget.get('fixture') else (rows if monitor.exists() else [])
  result={'pass':c0_pass,'steps':53851 if c0_pass else None,
          'rho_range':([min(float(x[1]) for x in rows),max(float(x[2]) for x in rows)]
             if not budget.get('fixture') and monitor.exists() and rows else None),
          'solver_rc':proc.returncode,'fixture_only':bool(budget.get('fixture'))}
  verdict=OUT/'C0_verdict.json';verdict.write_text(json.dumps(result)+'\n');seal(verdict)
  if monitor.exists():
   dest=OUT/'C0_rho_monitor.csv';shutil.copyfile(monitor,dest);seal(dest)
  print('C0_VERDICT',result,flush=True)
  cases={g:{} for g in GROUPS}
  order=tuple((g,'1') for g in (('K1a','K1b','K2','K3a','K3b') if c0_pass else ('K1a','K1b','K2')))
  verified_cases=[]
  for idx,(group,seed) in enumerate(order):
   label=group+'_s'+seed;exe,src=exes[group]
   # At each case boundary, use the last observed end-to-end rate if available.
   # The 30T bound includes 25T spin-up, all three 1T V0 extensions, 2T stats.
   rate=budget['steps_per_second'][group]
   if idx: rate=min(rate,budget['steps_per_T']*30/max(time.time()-case_start,1))
   worst=30*budget['steps_per_T']/rate+budget['per_case_overhead_s']
   margin=deadline-time.time()-worst-budget['teardown_s']
   print('BUDGET_MARGIN',label,margin,'RATE',rate,flush=True)
   if margin<=0:
    stop=OUT/'budget_stop.json';stop.write_text(json.dumps({'next_case':label,'margin_s':margin,'rate_step_s':rate,'verified':verified_cases})+'\n');seal(stop)
    break
   case_start=time.time()
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
       half=round(budget['steps_per_T']/2)
       pair,choice=decide(d,a,end,half,False)
       decision_seen.add(a);print('V0_DECISION',label,a,choice,pair,flush=True)
     time.sleep(.1 if mode=='fixture' else 1)
    if proc.returncode:seal(log);raise RuntimeError('solver failed '+label+' rc='+str(proc.returncode))
   seal(log)
   if not (d/'producer.done').exists():raise RuntimeError('missing producer.done '+label)
   result=summarize(d)
   validate_contract(result)
   # Descriptive full 2T windows from cold start; never call assert_T17 here.
   import math
   final_step=int(result['native_provenance']['statistics_end'])
   wcount=final_step//(2*budget['steps_per_T'])
   windows=[]
   for w in range(1,wcount+1):
    val=analyze(d,w,False);windows.append(val)
   wx=OUT/(label+'_windows.json');wx.write_text(json.dumps(windows,allow_nan=False)+'\n');seal(wx)
   x=OUT/(label+'_case.json');x.write_text(json.dumps(result,allow_nan=False)+'\n');seal(x)
   cases[group][seed]=result
   # Compact evidence only: plane binaries remain on VM; seal their hashes in summary.
   local_files=[p for p in d.iterdir() if p.is_file() and p.suffix in ('.csv','.txt','.ready','.decision','.done')]
   files=[]
   for source in local_files:
    target=OUT/(label+'_'+source.name)
    shutil.copyfile(source,target);seal(target);files.append(target)
   files.extend((log,x,wx))
   hashes={p.name:sha(p) for p in files}
   manifest=OUT/(label+'_handoff.json');manifest.write_text(json.dumps({'sha256':hashes})+'\n');seal(manifest)
   ack=OUT/(label+'.ack.json')
   while not ack.exists():
    if time.time()>=deadline-budget['teardown_s']:raise TimeoutError('missing ACK '+label)
    time.sleep(.1 if mode=='fixture' else 2)
   if json.loads(ack.read_text())!=hashes:raise RuntimeError('ACK mismatch '+label)
   print('HOST_VERIFIED',label,flush=True)
   verified_cases.append(label)
  done=OUT/'run.done';done.write_text(json.dumps({'verified':verified_cases,'budget_stop':len(verified_cases)<len(order),'c0_pass':c0_pass,'expected':list(label+'_s1' for label,_ in order)})+'\n');seal(done)
 except BaseException:
  x=OUT/'run.failed';x.write_text(traceback.format_exc());seal(x);raise

if __name__=='__main__':run()
