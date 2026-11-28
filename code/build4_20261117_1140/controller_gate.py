#!/usr/bin/env python3
"""Own one G4 allocation, poll and pull full gate evidence, stop safely."""
import pathlib,subprocess,time,json,hashlib,re,sys,traceback
R=pathlib.Path(__file__).resolve().parent;BASE=['colab','--auth','oauth2'];NAME='luw-t9b4-g4-1117-a1';CFG=R/'sessions.json';O=R/'evidence';E=R/'events.jsonl';EP=R/'endpoint.json'
def log(event,**data):
 line={'when':time.strftime('%m-%d %H:%M:%S %Z'),'event':event,**data}
 with E.open('a') as f:f.write(json.dumps(line,ensure_ascii=False)+'\n')
 print(json.dumps(line,ensure_ascii=False),flush=True)
def call(args,timeout=140):
 p=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
 log('cmd',action=args[args.index('--config')+2] if '--config' in args else args[-1],code=p.returncode,tail=p.stdout[-450:]);return p.stdout,p.returncode
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def endpoints(t):return set(re.findall(r'gpu-g4-s-[a-z0-9-]+',t,re.I))
def cli(args,timeout=140):return call(BASE+['--config',str(CFG)]+args,timeout)
def main():
 assert not E.exists() and not CFG.exists() and not O.exists() and not EP.exists()
 for p in ('t9b4_source.tar.gz','t9b4_manifest.json','worker_gate.py','launch_gate.py','probe_gate.py'):assert (R/p).is_file()
 manifest=json.loads((R/'t9b4_manifest.json').read_text());assert sha(R/'t9b4_source.tar.gz')==manifest['archive_sha256']
 O.mkdir();(R/'.colab_owner').open('x').write('#4656964a build4 / researchos-uwind-luw / '+NAME+'\n')
 alloc=time.time();attempt=0;created=None;ep=None;terminal=None;verified=set();deadline=None
 while time.time()-alloc<14400:
  attempt+=1;view,_=call(BASE+['sessions']);assert NAME not in view
  before=endpoints(view);log('alloc_attempt',attempt=attempt)
  try:resp,rc=cli(['new','-s',NAME,'--gpu','G4'],180)
  except subprocess.TimeoutExpired:log('alloc_ambiguous');return 2
  if rc:
   view,_=call(BASE+['sessions']);
   if NAME in view or endpoints(view)-before:log('alloc_ambiguous_presence',view=view[-500:]);return 2
   if not re.search('503|412|refused|unavailable|precondition',resp,re.I):return 2
   log('alloc_refused',attempt=attempt,response=resp[-300:]);time.sleep(min(1200,max(0,alloc+14400-time.time())));continue
  created=time.time();deadline=created+4.55*3600/6.81 # stop with reserve under 5 CU
  view,_=call(BASE+['sessions']);new=endpoints(view)-before
  if len(new)!=1:log('endpoint_ambiguous',view=view[-500:]);return 2
  ep=next(iter(new));EP.write_text(json.dumps({'endpoint':ep,'created':created,'deadline':deadline,'assumed_CU_per_h':6.81,'session':NAME})+'\n');log('allocated',endpoint=ep,deadline=deadline)
  break
 if not created:log('allocation_window_expired');return 2
 def pull(remote,local):
  p=O/local
  if p.exists():return p
  try:msg,code=cli(['download','-s',NAME,remote,str(p)],180)
  except subprocess.TimeoutExpired:log('download_timeout',file=local);return None
  return p if not code and p.is_file() else None
 try:
  uploads={p:R/p for p in ('t9b4_source.tar.gz','t9b4_manifest.json','worker_gate.py','launch_gate.py','probe_gate.py')}
  old=R.parent
  uploads.update({'t9b2_stage.tar.gz':old/'t9b2_stage.tar.gz','t9b2_archive.json':old/'t9b2_archive.json','t5_reference_worker.py':old.parent/'R21.4a_T5_caseE_WM_retry1/worker.py','remote_worker_run2.py':old.parent/'R21.4a_T3_emptyground/run2/remote_worker_run2.py'})
  for p,source in uploads.items():
   text,code=cli(['upload','-s',NAME,str(source),'/content/'+p],180)
   if code:raise RuntimeError('upload '+p+' '+text[-200:])
  # The remote launcher has an exclusive marker; an exec timeout must not relaunch.
  try:msg,code=cli(['exec','-s',NAME,'-f',str(R/'launch_gate.py')],130)
  except subprocess.TimeoutExpired:msg='';code=1;log('launch_timeout_ambiguous')
  if code or 'LAUNCHED' not in msg:
   probe,_=cli(['exec','-s',NAME,'-f',str(R/'probe_gate.py')],130)
   if '"pid": null' in probe or 'PROBE ' not in probe:raise RuntimeError('launch unconfirmed; keep session until deadline')
  ka=[str(pathlib.Path.home()/'bin/colab-keepalive'),'--config',str(CFG),'-s',NAME,'--log','/content/t9b4.log','--proc','/content/worker_gate.py','--until-marker','/content/t9b4/out/run.done','--max-hours','1','--expect-hours','1','--no-remind','--final-pull','/content/t9b4.log:'+str(O),'--detach']
  msg,code=call(ka,90);log('keepalive_start',code=code,detail=msg[-500:])
  if code:raise RuntimeError('keepalive failed; inspect live session')
  absent=0
  while time.time()<deadline-150:
   try:
    reply,code=cli(['exec','-s',NAME,'-f',str(R/'probe_gate.py')],120)
    state=json.loads(next(x[6:] for x in reply.splitlines() if x.startswith('PROBE ')));absent=0
    log('probe',files=list(state['ready']),done=state['done'],failed=state['failed'],tail=state['log'][-180:])
    for name,info in state['ready'].items():
     if name in verified:continue
     p=pull('/content/t9b4/out/'+name,name);side=pull('/content/t9b4/out/'+name+'.sha256',name+'.sha256')
     if p and side and p.stat().st_size==info['size'] and sha(p)==side.read_text().strip()==info['sha']:
      verified.add(name);log('verified',file=name,sha=info['sha'])
    if state['done'] or state['failed']:
     terminal='done' if state['done'] else 'failed'
     if set(state['ready'])<=verified:break
   except (subprocess.TimeoutExpired,ValueError,StopIteration,RuntimeError) as ex:
    log('probe_error',error=str(ex)[-250:]);view,_=call(BASE+['sessions']);absent=absent+1 if ep not in endpoints(view) else 0
    if absent>=3:log('endpoint_absent_three',endpoint=ep);break
   time.sleep(30)
  if terminal or time.time()>=deadline-150 or absent>=3:
   for remote in ('/content/t9b4.log','/content/t9b4/out/run.failed','/content/t9b4/out/run.done'):
    pull(remote,pathlib.Path(remote).name)
   if absent<3:
    msg,code=cli(['stop','-s',NAME],150);log('stop',code=code,response=msg[-200:])
   view,_=call(BASE+['sessions']);released=ep not in endpoints(view)
   log('stop_check',endpoint=ep,released=released,terminal=terminal,verified=sorted(verified),estimated_CU=(time.time()-created)*6.81/3600)
   msg,code=call([str(pathlib.Path.home()/'bin/colab-orphans')],90);log('orphans',code=code,result=msg[-500:]);return 0 if terminal=='done' and released else 2
  log('LIVE_UNCERTAIN',endpoint=ep,deadline=deadline);return 2
 except BaseException as ex:
  log('controller_exception',error=repr(ex),trace=traceback.format_exc()[-1000:],endpoint=ep,deadline=deadline)
  # Never stop a potentially running worker merely because a probe failed.
  return 2
if __name__=='__main__':sys.exit(main())
