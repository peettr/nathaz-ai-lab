#!/usr/bin/env python3.10
"""Bounded Colab owner/controller; no restart after ambiguous launch."""
import pathlib,subprocess,json,time,re,sys,hashlib,traceback,shutil
R=pathlib.Path(__file__).resolve().parent; BASE=['colab','--auth','oauth2'];NAME_BASE='luw-t9b2-g4-1117';E=R/'build2_events.jsonl'
EXPECTED={'cube_trace.csv','cube_metrics.json','on_cube_actual_opencl.cl','on_city_actual_opencl.cl','off_city_actual_opencl.cl','on_city_flags.npz','off_city_flags.npz','points80.json','gate1.json'}
def log(ev,**kw):
 row={'local_time':time.strftime('%m-%d %H:%M:%S %Z'),'event':ev,**kw}
 with E.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
 print(ev,kw,flush=True)
def call(a,timeout=130,check=False):
 p=subprocess.run(a,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
 out=p.stdout;log('command',command=' '.join(a[:7]),rc=p.returncode,tail=out[-420:])
 if check and p.returncode:raise RuntimeError('command failed '+out[-500:])
 return out,p.returncode
def endpoints(text):return set(re.findall(r'gpu-(?:g4|a100)-s-[a-z0-9-]+',text,re.I))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def dryrun():
 assert not E.exists()
 for n in ('t9b2_stage.tar.gz','t9b2_archive.json','worker_build2.py','probe_build2.py','launch_build2.py'):
  assert (R/n).is_file(),n
 meta=json.loads((R/'t9b2_archive.json').read_text()); assert sha(R/'t9b2_stage.tar.gz')==meta['archive_sha256']
 import tarfile
 with tarfile.open(R/'t9b2_stage.tar.gz') as t:
  names={x.name for x in t.getmembers()};assert all('stage/'+p in names for p in meta['members'])
 import py_compile
 for n in ('worker_build2.py','probe_build2.py','launch_build2.py'):py_compile.compile(str(R/n),doraise=True)
 print('PRECHECK PASS source archive scripts and members',len(meta['members']))
def run():
 dryrun()
 allocation_start=time.time();spent_s=0.; attempts=[]
 for k in range(13):
  if time.time()-allocation_start>=4*3600:break
  gpu='G4' if k==0 or not attempts or attempts[-1]['gpu']=='A100' else 'A100'
  # Only try A100 after a definite G4 refusal; thereafter alternate each retry round.
  name=NAME_BASE+'-a'+str(k+1);D=R/('build2_attempt_'+str(k+1));D.mkdir(exist_ok=False)
  cfg=D/'sessions.json';L=BASE+['--config',str(cfg)];(D/'.colab_owner').open('x').write('R21.4a T9b-build2 luw '+name+'\n')
  view,_=call(BASE+['sessions']);assert name not in view
  before=endpoints(view)
  try:text,rc=call(L+['new','-s',name,'--gpu',gpu],180)
  except subprocess.TimeoutExpired:
   log('allocation_ambiguous',name=name);return False
  if rc!=0:
   if not re.search('503|412|Allocation refused|Service Unavailable|Precondition Failed',text,re.I):
    log('allocation_other_error',name=name,tail=text[-400:]);return False
   view,_=call(BASE+['sessions']);assert name not in view
   attempts.append({'name':name,'gpu':gpu,'status':'definite_refusal'})
   log('allocation_refused',name=name,gpu=gpu)
   if gpu=='G4':continue
   if time.time()-allocation_start+1200>4*3600:break
   time.sleep(1200);continue
  if 'Session READY' not in text:log('allocation_ambiguous_receipt',name=name,tail=text[-400:]);return False
  created=time.time(); rate=6.81 if gpu=='G4' else 5.4
  budget_left=6.0-spent_s*rate/3600
  # Limit based on verified historical rate; reserve 0.25 CU teardown.
  deadline=created+max(0,(budget_left-0.25)*3600/rate)
  view,_=call(BASE+['sessions']);new_eps=endpoints(view)-before
  if len(new_eps)!=1:log('endpoint_ambiguous',name=name,view=view[-600:]);return False
  ep=next(iter(new_eps));log('allocated',name=name,gpu=gpu,endpoint=ep,created=created,deadline=deadline,assumed_rate=rate)
  O=D/'evidence';O.mkdir(exist_ok=False);verified=set();terminal=False;absent=0;launched=False
  def local(a,timeout=140,check=True):return call(L+a,timeout,check)[0]
  def pull(remote,name,required=False):
   p=O/name
   if not p.exists():
    try:local(['download','-s',name_session,remote,str(p)],240,required)
    except (RuntimeError,subprocess.TimeoutExpired,OSError) as e:
     log('pull_error',file=name,error=str(e)[-250:]);return None
   return p if p.is_file() else None
  name_session=name
  try:
   for f in ('t9b2_stage.tar.gz','t9b2_archive.json','worker_build2.py','probe_build2.py','launch_build2.py'):
    local(['upload','-s',name,str(R/f),'/content/'+f],180)
   # Upload read-only prior sampling definition as a module.
   local(['upload','-s',name,str(R.parent/'R21.4a_T5_caseE_WM_retry1/worker.py'),'/content/t5_reference_worker.py'],180)
   local(['upload','-s',name,str(R.parent/'R21.4a_T3_emptyground/run2/remote_worker_run2.py'),'/content/remote_worker_run2.py'],180)
   local(['upload','-s',name,str(R.parent/'R21.4a_T5_caseE_WM_retry1/gpu_probe.py'),'/content/gpu_probe.py'],180)
   gpuinfo=local(['exec','-s',name,'-f',str(R.parent/'R21.4a_T5_caseE_WM_retry1/gpu_probe.py')],110)
   details=next((json.loads(x[4:]) for x in gpuinfo.splitlines() if x.startswith('GPU ')),None)
   assert details and details['memory_total_mb']>=20000 and details['memory_free_mb']>=15000 and details['max_alloc_mb']>=9000
   assert time.time()+2200<deadline,'remaining CU insufficient for city gate plus transfer'
   try:receipt=local(['exec','-s',name,'-f',str(R/'launch_build2.py')],150)
   except (subprocess.TimeoutExpired,RuntimeError):receipt='';log('launch_uncertain',name=name)
   if 'LAUNCHED' not in receipt:
    state=local(['exec','-s',name,'-f',str(R/'probe_build2.py')],120)
    assert 'PROBE ' in state and ('t9b2.log' in state or 'READY' in state or 'BUILD' in state),'unconfirmed launch'
   launched=True
   ka=[str(pathlib.Path.home()/'bin/colab-keepalive'),'--config',str(cfg),'-s',name,'--log','/content/t9b2.log','--proc','/content/worker_build2.py','--until-marker','/content/t9b2/out/run.done','--max-hours','2','--expect-hours','1','--no-remind','--final-pull','/content/t9b2.log:'+str(O),'--detach']
   log('keepalive',receipt=call(ka,100,True)[0][-400:])
   while time.time()<deadline-120:
    try:
     reply=local(['exec','-s',name,'-f',str(R/'probe_build2.py')],110)
     state=json.loads(next(x[6:] for x in reply.splitlines() if x.startswith('PROBE ')));absent=0
    except (subprocess.TimeoutExpired,RuntimeError,ValueError,StopIteration) as q:
     log('probe_error',error=str(q)[-300:]);view,_=call(BASE+['sessions']);absent=absent+1 if ep not in endpoints(view) else 0
     if absent>=3:log('endpoint_absent_3',endpoint=ep);break
     time.sleep(40);continue
    log('probe',files=list(state['ready']),done=state['done'],failed=state['failed'],tail=state['log'][-220:])
    for key,info in state['ready'].items():
     f=key[:-7]
     if f in verified:continue
     p=pull('/content/t9b2/out/'+f,f);side=pull('/content/t9b2/out/'+key,key)
     if p and side and p.stat().st_size==info['size'] and sha(p)==info['sha']==side.read_text().strip():verified.add(f);log('verified',file=f,sha256=info['sha'])
     else:log('verification_pending',file=f)
    if state['done'] or state['failed']:
     terminal=True
     if all(key[:-7] in verified for key in state['ready']):break
    time.sleep(40)
  except BaseException as q:
   log('controller_error',error=str(q)[-500:],traceback=traceback.format_exc()[-1000:])
  # State exceptions do not authorize a stop. Only verified terminal, deadline, or absent endpoint.
  if terminal and all(key[:-7] in verified for key in state['ready']) or time.time()>=deadline-120 or absent>=3:
   for remote in ('/content/t9b2.log','/content/t9b2/out/run.done','/content/t9b2/out/run.failed'):
    pull(remote,pathlib.Path(remote).name)
   if absent<3:local(['stop','-s',name],150,False)
   view,_=call(BASE+['sessions']);released=ep not in endpoints(view)
   log('stop_check',endpoint=ep,released=released,verified=sorted(verified),estimated_CU=(time.time()-created)*rate/3600)
   o,rc=call([str(pathlib.Path.home()/'bin/colab-orphans')],100);log('orphans',tail=o[-700:],rc=rc)
   if not released:return False
   return bool(terminal and state['done'] and EXPECTED.issubset(verified))
  log('LIVE_UNCERTAIN',endpoint=ep,deadline=deadline,verified=sorted(verified));return False
 log('allocation_window_expired',attempts=attempts);return False
if __name__=='__main__':sys.exit(0 if run() else 2)
