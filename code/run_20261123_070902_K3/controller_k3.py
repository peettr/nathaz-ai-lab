#!/usr/bin/env python3
"""T17 T15 pair: Linux-spooled Colab controller; no other session ownership."""
import argparse, hashlib, json, os, pathlib, re, shutil, subprocess, sys, time, uuid
R=pathlib.Path(__file__).resolve().parent
ARCHIVE=pathlib.Path(os.environ['T17_ARCHIVE_ROOT'])
BASE=['colab','--auth','oauth2']; RATE=5.4; CAP=6.5
PAYLOAD=('worker_native.py','native_analysis.py','analyze_longspin.py','remote_B.py','assert_T17.py','t17b_stage.tar.gz','t17b_manifest.json','t17b_budget.json')
CASES=('K3a_s1','K3b_s1')
def log(*args):print(time.strftime('%Y-%m-%d %H:%M:%S'),*args,flush=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def cmd(a,timeout=45):
 try:
  r=subprocess.run(a,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=max(.1,timeout))
  return r.returncode,r.stdout
 except subprocess.TimeoutExpired as e:return 124,'AMBIGUOUS_TIMEOUT '+str(e)
def sync():
 """Never keep project-mount handles open; retries cannot kill paid session."""
 for p in R.rglob('*'):
  if not p.is_file() or p.name.endswith('.partial') or p.name=='sessions.json' or p.name.startswith('exec_'):continue
  rel=p.relative_to(R);q=ARCHIVE/rel
  for attempt in range(4):
   try:
    if q.is_file() and sha(q)==sha(p):break
    q.parent.mkdir(parents=True,exist_ok=True)
    tmp=q.with_name(q.name+'.sync_'+uuid.uuid4().hex)
    shutil.copyfile(p,tmp)
    if sha(tmp)!=sha(p):raise IOError('sync SHA mismatch')
    if q.exists():
     # Only this newly created archive root is writable; preserve older milestone.
     if sha(q)!=sha(p):raise IOError('different archived milestone '+str(q))
     tmp.unlink()
    else:tmp.rename(q)
    break
   except OSError as e:
    log('MOUNT_SYNC_RETRY',rel,attempt,repr(e));time.sleep(10)

def main():
 plan=json.loads((R/'SESSION_PLAN.json').read_text())
 seal=json.loads((R/'PREFLIGHT.ok').read_text())
 for n,h in seal.items():
  if sha(R/n)!=h:raise RuntimeError('sealed source mismatch '+n)
 if not (R/'NATIVE_PRODUCER_APPROVED.ok').exists():raise RuntimeError('producer not approved')
 if plan['full_chain_upper_CU']>=CAP:raise RuntimeError('preallocation budget insufficient')
 before=cmd(BASE+['sessions'])[1]
 owner=R/'.colab_owner';owner.open('x').write('T18 C01 #9ab25d8a; researchos-uwind-luw\n')
 sync();window=time.time();spent=0;attempt_number=0
 while time.time()-window<4*3600:
  attempt_number+=1
  if spent+plan['first_case_upper_CU']>=CAP:
   log('BUDGET_STOP_BEFORE_ALLOCATION',spent);return 2
  name='luw-t18k3-'+uuid.uuid4().hex[:9];d=R/('session_'+name);d.mkdir();e=d/'evidence';e.mkdir();cfg=d/'sessions.json'
  def cli(args,timeout=45):return cmd(BASE+['--config',str(cfg),args[0],'-s',name]+args[1:],timeout)
  stamp=time.time();rc,msg=cli(['new','--gpu','A100'],100);log('ALLOC',attempt_number,name,rc,msg[-1400:])
  global_list=cmd(BASE+['sessions'])[1];private=cmd(BASE+['--config',str(cfg),'sessions'])[1]
  found=set(re.findall(r'gpu-a100-[a-z0-9-]+','\n'.join(line for line in private.splitlines() if name in line)+'\n'+msg))
  owned=[x for x in found if x in global_list and x not in before]
  if len(owned)!=1:
   if rc==0 or found or name in private or not re.search(r'503|412|Service Unavailable|Allocation refused|Precondition Failed',msg,re.I):
    log('AMBIGUOUS_ALLOCATION_DO_NOT_RETRY',name,found);sync();return 2
   log('DEFINITE_REFUSAL',name);sync()
   if time.time()-window+1200>=4*3600:break
   time.sleep(max(0,stamp+1200-time.time()));continue
  ep=owned[0];created=stamp;hard=created+(CAP-spent)*3600/RATE;cut=hard-90
  watchdog=created+900;started=False;verified={};acked=[];result='unconfirmed';keepalive=False
  log('OWNED_ENDPOINT',ep,'cut',cut,'watchdog',watchdog);sync()
  def bounded(args,seconds=50):
   if time.time()>=cut:raise TimeoutError('CU cut')
   return cli(args,min(seconds,cut-time.time()))
  def checked(pair):
   rc,s=pair
   if rc:raise OSError('COLAB '+str(rc)+' '+s[-900:])
   return s
  def retry(kind,fn,prestart=False):
   for i in range(5):
    try:return fn()
    except (OSError,TimeoutError) as ex:
     log('RETRY',kind,i,repr(ex));sync()
     if time.time()>=cut or (prestart and time.time()>=watchdog):raise
     if i==4:raise
     time.sleep(min(30*2**i,max(0,(watchdog if prestart else cut)-time.time())))
  def upload(path,n):return retry('upload '+n,lambda:checked(bounded(['upload',str(path),'/content/'+n],65)),not started)
  def remote(code):
   f=d/('exec_'+uuid.uuid4().hex+'.py');f.write_text("import sys;sys.path.insert(0,'/content')\nimport remote_B as io\n"+code+'\n')
   return retry('exec',lambda:checked(bounded(['exec','-f',str(f)],55)),not started)
  def probe():
   out=remote("print('T17_PROBE '+io.json.dumps(io.probe(io.C)),flush=True)")
   vals=[line[len('T17_PROBE '):] for line in out.splitlines() if line.startswith('T17_PROBE ')]
   if len(vals)!=1:raise OSError('probe tag missing')
   return json.loads(vals[0])
  def download(n):
   target=e/(n+'.partial')
   retry('download '+n,lambda:checked(bounded(['download','/content/t17b/out/'+n,str(target)],65)))
   return target
  def collect():
   missing=0
   while time.time()<cut:
    try:
     entries=probe();missing=0
     for n,info in entries.items():
      if n in verified:continue
      if not re.fullmatch(r'[\w.-]+',n):raise ValueError('unsafe filename')
      f=download(n);side=download(n+'.sha256');h=sha(f)
      if h!=info['sha'] or h!=side.read_text().strip() or f.stat().st_size!=info['size']:raise OSError('SHA/size '+n)
      f.rename(e/n);side.rename(e/(n+'.sha256'));verified[n]=h;log('VERIFIED',n,h)
     for label in CASES[len(acked):]:
      hand=label+'_handoff.json'
      if hand not in verified:break
      hashes=json.loads((e/hand).read_text())['sha256']
      if not set(hashes)<=set(verified) or any(verified[k]!=v for k,v in hashes.items()):break
      pending=d/(label+'.ack.pending');pending.write_text(json.dumps(hashes))
      upload(pending,pending.name);remote('io.ack(io.C,'+repr(label)+')');acked.append(label)
      log('ACK',label);sync()
     if 'run.failed' in verified:return 'failed'
     if 'run.done' in verified:
      done=json.loads((e/'run.done').read_text());names=done['verified']
      c0='C0_verdict.json'
      if c0 not in verified or 'C0_K3a_solver.log' not in verified or any(g+'_opencl_compilecheck.log' not in verified for g in ('K3a','K3b')):return 'failed'
      smoke=json.loads((e/c0).read_text())
      if smoke.get('fixture_only'):return 'failed'
      if smoke.get('pass') and 'C0_rho_monitor.csv' not in verified:return 'failed'
      expected=list(CASES if smoke.get('pass') else ())
      if names!=expected[:len(names)] or acked!=names or any(x+'_case.json' not in verified or x+'_windows.json' not in verified for x in names):return 'failed'
      if not done.get('budget_stop') and names!=expected:return 'failed'
      return 'budget_stop' if done.get('budget_stop') else 'done'
    except (OSError,TimeoutError) as ex:
     log('PROBE_FAILURE_NO_STOP',repr(ex));sync()
     # Probe cannot stop a started worker; session absence must be confirmed 3 times.
     global_rc,global_text=cmd(BASE+['sessions'],35)
     if global_rc==0 and ep not in global_text:missing+=1
     else:missing=0
     if missing>=3:return 'session_absent'
    time.sleep(min(8,max(0,cut-time.time())))
   return 'deadline'
  try:
   # Every pre-worker call is bounded by a 15-minute launch watchdog.
   machine=retry('machine',lambda:checked(bounded(['exec','-f',str(R/'machine.py')],50)),True)
   vals=[x[len('GPU_MACHINE '):] for x in machine.splitlines() if x.startswith('GPU_MACHINE ')]
   if len(vals)!=1:raise ValueError('machine probe missing')
   info=json.loads(vals[0]);g=re.fullmatch(r'([^,]+),\s*(\d+),\s*(\d+)',info['stdout'].strip()) if info['rc']==0 else None
   if not g or 'A100' not in g[1] or int(g[3])<12000:raise ValueError('actual GPU/VRAM not A100')
   log('MACHINE',g.groups())
   budget=d/'t17b_budget.json'
   budget.write_text(json.dumps({'mode':'production','work_deadline':cut,'steps_per_T':plan['steps_per_T'],'steps_per_second':plan['steps_per_second'],'per_case_overhead_s':plan['per_case_overhead_s'],'teardown_s':90})+'\n')
   for n in PAYLOAD:upload(budget if n=='t17b_budget.json' else R/n,n)
   receipt=d/'t17b_upload.json';receipt.write_text(json.dumps({n:sha(budget if n=='t17b_budget.json' else R/n) for n in PAYLOAD}))
   upload(receipt,receipt.name)
   margin=cut-time.time()-(plan['full_chain_upper_s'])
   log('PRELAUNCH_K3_TWO_CASE_MARGIN_S',margin)
   if margin<=0:raise TimeoutError('full chain prelaunch budget cannot fit')
   # Ambiguous launch timeout is reconciled by reading remote exclusive marker.
   try:reply=remote('io.launch(io.C)')
   except (OSError,TimeoutError):
    reply=remote("print('LAUNCH_MARKER',io.C.joinpath('t17b.launch').read_text() if io.C.joinpath('t17b.launch').exists() else 'ABSENT')")
   log('LAUNCH_REPLY',reply[-500:])
   def worker_alive():
    s=remote("import os; p=io.C/'t17b.launch'; v=p.read_text().strip() if p.exists() else '';print('WORKER_ACK',v,os.path.exists('/proc/'+v) if v else False)")
    return any(x.startswith('WORKER_ACK ') and x.endswith(' True') for x in s.splitlines())
   while not worker_alive() and time.time()<watchdog:time.sleep(10)
   if time.time()>=watchdog:raise TimeoutError('15m startup watchdog: worker ACK absent')
   started=True;log('WORKER_STARTED_ACK',name);sync()
   kc=[str(pathlib.Path.home()/'bin/colab-keepalive'),'--config',str(cfg),'-s',name,'--log','/content/t17b.log','--until-marker','/content/t17b/out/run.done','--max-hours','3','--expect-hours','3','--no-remind','--pull','/content/t17b.log:'+str(d/'worker_progress.log'),'--final-pull','/content/t17b/out/*.json:'+str(d/'final'),'--final-pull','/content/t17b/out/*.csv:'+str(d/'final'),'--final-pull','/content/t17b/out/*.sha256:'+str(d/'final'),'--detach']
   krc,kmsg=cmd(kc,60);keepalive=krc==0;log('KEEPALIVE',krc,kmsg[-500:]);sync()
   if not keepalive:log('KEEPALIVE_NOT_ARMED: collecting actively')
   result=collect()
  except BaseException as ex:
   log('CONTROLLER_EXCEPTION',repr(ex),'worker_started',started);sync()
   if started and time.time()<cut:result=collect()
   elif not started:result='startup_watchdog'
  finally:
   if started and result not in ('done','failed','deadline','budget_stop','session_absent') and time.time()<cut:result=collect()
   log('STOP_REASON',result)
   if result not in ('done','failed','deadline','budget_stop','session_absent','startup_watchdog'):
    log('UNCONFIRMED_NO_STOP');sync();return 2
   released=False
   if result=='session_absent':released=True
   else:
    for i in range(3):
     rc,s=cli(['stop'],max(1,min(35,hard-time.time())));log('STOP',i,rc,s[-300:])
     rc,s=cmd(BASE+['sessions'],30)
     if rc==0 and ep not in s:released=True;break
   log('ENDPOINT',ep,'RELEASED',released)
   if keepalive:log('KEEPALIVE_STOP',cmd(['systemctl','--user','stop','colab-keepalive-'+name],20)[0])
   log('ORPHANS',cmd([str(pathlib.Path.home()/'bin/colab-orphans')],40))
   spent+=(time.time()-created)*RATE/3600 if released else CAP
   log('CU_ESTIMATE',spent,'NOT_BILLING');sync()
  if result in ('done','budget_stop'):return 0 if released else 2
  if result=='startup_watchdog' and released and spent+plan['first_case_upper_CU']<CAP:
   before=cmd(BASE+['sessions'])[1]
   continue
  return 2
 return 2
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--authorized-run',action='store_true')
 a=parser.parse_args()
 if not a.authorized_run:raise SystemExit('inert without --authorized-run')
 log('LINUX_SPOOL',R,'ARCHIVE',ARCHIVE)
 sys.exit(main())
