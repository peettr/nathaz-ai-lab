#!/usr/bin/env python3
"""T17 A-iv four periodic builds and ordered engineering gates."""
import argparse,csv,hashlib,json,os,pathlib,shutil,subprocess,tarfile,time,traceback
C=pathlib.Path('/content')
VARIANTS=('periodic_bounce','periodic_t4','periodic_t15_k2','periodic_t15_k3')
STAGES=(('a1a','periodic_t15_k2',1000),('a1b','periodic_t15_k2',1000),('a3','periodic_t15_k2',0),('a7','periodic_t15_k2',8975),('speed_bounce','periodic_bounce',2000),('speed_t4','periodic_t4',2000),('speed_t15','periodic_t15_k2',2000))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def seal(p):
 (p.parent/(p.name+'.sha256')).write_text(sha(p)+'\n');print('READY',p.name,sha(p),flush=True)
def execute(c,stub=None):
 budget=json.loads((c/'t17_budget.json').read_text()); fixture=budget['mode']=='fixture';deadline=budget['work_deadline']
 if fixture != bool(stub):raise ValueError('fixture/stub mismatch')
 man=json.loads((c/'t17_manifest.json').read_text());arc=c/'t17_stage.tar.gz'
 if sha(arc)!=man['archive_sha256']:raise ValueError('archive hash mismatch')
 o=c/'t17/out';o.mkdir(parents=True,exist_ok=False)
 try:
  with tarfile.open(arc) as t:
   for m in t:
    p=pathlib.PurePosixPath(m.name)
    if not p.parts or p.parts[0]!='pack_stage' or '..' in p.parts or not(m.isdir() or m.isfile()):raise ValueError('unsafe tar member')
   t.extractall(c/'t17',filter='data')
  stage=c/'t17/pack_stage';exes={}
  # Native compile for every macro variant before any solver step.
  for name in VARIANTS:
   src=stage/name
   for file,h in man['variants'][name].items():
    if sha(src/'src'/file)!=h:raise ValueError('source hash mismatch '+name+'/'+file)
   log=o/(name+'_host_build.log')
   with log.open('x') as f:rc=subprocess.run(['make','Linux','-j8'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=500).returncode
   seal(log)
   if rc:raise RuntimeError('host build failed '+name)
   exe=src/'bin/FluidX3D'
   if not exe.is_file():raise RuntimeError('missing binary '+name)
   if stub:shutil.copyfile(stub,exe);exe.chmod(0o755)
   exes[name]=exe
   cl=o/(name+'_gpu_compile.log')
   env={**os.environ,'T17_STAGE_A_ALLOW':'1','LUW_COMPILE_ONLY':'1','LD_LIBRARY_PATH':str(src/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
   with cl.open('x') as f:rc=subprocess.run([str(exe)],cwd=src,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=120).returncode
   seal(cl)
   if rc or (not fixture and 'COMPILE_ONLY PASS' not in cl.read_text(errors='replace')):raise RuntimeError('native compile failed '+name)
  print('ALL_NATIVE_COMPILE_PASS',flush=True)
  # Production cut, not fixture-zero. Abort before starting a stage when evidence cannot fit.
  estimates={'a1a':45,'a1b':45,'a3':25,'a7':300,'speed_bounce':70,'speed_t4':70,'speed_t15':70}
  done=[];elapsed={}
  for j,(label,variant,steps) in enumerate(STAGES):
   need=sum(estimates[x[0]] for x in STAGES[j:])+90
   margin=deadline-time.time()-need
   print('BUDGET_STAGE',label,'margin_s',round(margin,3),'need_s',need,flush=True)
   if margin<=0:raise TimeoutError('stage budget insufficient '+label)
   src=stage/variant;log=o/(label+'_solver.log');ledger=o/(label+'_ledger.csv')
   env={**os.environ,'T17_STAGE_A_ALLOW':'1','T17_LEDGER_CSV':str(ledger),'T17_DIAGNOSTIC_STEPS':str(steps),
        'T17_A1B_MIRROR_UNFORCED':'1' if label=='a1b' else '0','LD_LIBRARY_PATH':str(src/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
   start=time.time()
   with log.open('x') as f:rc=subprocess.run([str(exes[variant])],cwd=src,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=min(estimates[label],max(1,deadline-time.time()-75))).returncode
   elapsed[label]=time.time()-start
   seal(log)
   if ledger.is_file():seal(ledger)
   if rc:raise RuntimeError('solver failed '+label+' rc='+str(rc))
   if not ledger.is_file():raise RuntimeError('native ledger absent '+label)
   gate=o/(label+'_gate.json')
   if label=='a1a':args=['--mode','a1a']
   elif label=='a1b':args=['--mode','a1b']
   elif label=='a3':args=['--mode','a3']
   elif label=='a7':
    import re
    m=re.search(r'force_per_volume_lattice=([\d.eE+-]+).*?half_turnover_steps=([\d.eE+-]+)',log.read_text(errors='replace'),re.S)
    if not m:raise RuntimeError('unit readback absent '+label)
    args=['--mode','a7','--force',m[1],'--half-steps',str(steps),'--group','t15']
   else:args=['--mode','a3']
   # Assert based on real native producer file; the fixture stub is only wiring proof.
   gate_stdout=o/(label+'_assert.log')
   with gate_stdout.open('x') as f:grc=subprocess.run(['python3',str(c/'assert_ledger.py'),str(ledger),*args,'--out',str(gate)],stdout=f,stderr=subprocess.STDOUT).returncode
   seal(gate_stdout)
   if gate.is_file():seal(gate)
   if grc:raise RuntimeError('gate failed '+label+' rc='+str(grc))
   hand=o/(label+'_handoff.json'); files=[log,ledger,gate]
   if j==0:files += [o/(x+'_gpu_compile.log') for x in VARIANTS]
   hashes={p.name:sha(p) for p in files};hand.write_text(json.dumps({'sha256':hashes})+'\n');seal(hand)
   ack=o/(label+'.ack.json')
   while not ack.exists():
    if time.time()+15>deadline:raise TimeoutError('host ACK '+label)
    time.sleep(.15 if fixture else 2)
   if json.loads(ack.read_text())!=hashes:raise RuntimeError('ACK mismatch '+label)
   print('HOST_VERIFIED',label,flush=True);done.append(label)
  result=o/'run.done';result.write_text(json.dumps({'verified_cases':done,'elapsed_s':elapsed})+'\n');seal(result)
 except BaseException:
  fail=o/'run.failed';fail.write_text(traceback.format_exc());seal(fail);raise
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--content',type=pathlib.Path,default=C);a.add_argument('--stub',type=pathlib.Path);v=a.parse_args();execute(v.content.resolve(),v.stub.resolve() if v.stub else None)
