#!/usr/bin/env python3.10
"""T5 owned Colab controller; probe timeout is uncertain, never an implicit stop."""
import pathlib,subprocess,json,time,hashlib,traceback,sys,re
R=pathlib.Path(__file__).resolve().parent;CFG=R/'sessions.json';NAME='luw-r214a-t5-casee-retry1-1117';O=R/'evidence';EVENT=R/'events.jsonl'
BASE=['colab','--auth','oauth2'];LOCAL=BASE+['--config',str(CFG)]
LABELS=[f'E_s{s}_{m}' for s in (101,102) for m in ('off','on')]
ENDPOINT=None;created=None;deadline=None;rate=None;GPU=None;verified=set();launched=False
def log(ev,**kw):
 row={'time':time.strftime('%m-%d %H:%M:%S %Z'),'event':ev,**kw}
 with EVENT.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
 print(ev,kw,flush=True)
def cmd(argv,timeout=120,check=True):
 p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout,stdin=subprocess.DEVNULL)
 log('command',argv=argv[:7],rc=p.returncode,tail=p.stdout[-420:])
 if check and p.returncode:raise RuntimeError(f'failed {argv[:7]} {p.stdout[-500:]}')
 return p.stdout,p.returncode
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def endpoints(s):return set(re.findall(r'gpu-(?:a100|g4)-s-[a-z0-9-]+',s,re.I))
def global_presence():return ENDPOINT in endpoints(cmd(BASE+['sessions'],90)[0])
def exec_file(p,env=None,timeout=110):
 args=LOCAL+['exec','-s',NAME,'-f',str(p)]
 for k,v in (env or {}).items():args+=['--env',k+'='+str(v)]
 return cmd(args,timeout)[0]
def probe_once():
 text=exec_file(R/'probe.py');lines=[x for x in text.splitlines() if x.startswith('PROBE ')]
 if not lines:raise RuntimeError('probe missing '+text[-200:])
 return json.loads(lines[-1][6:])
def monitor_once(probe,check,sleep=lambda _:None):
 try:return probe(),False
 except (subprocess.TimeoutExpired,RuntimeError,ValueError,OSError) as e:
  log('probe_error',error=str(e)[-350:])
  try:
   status=cmd(LOCAL+['status','-s',NAME],70,False)[0];log('named_status',tail=status[-250:])
   absent=not check();log('global_reconcile',absent=absent)
  except (subprocess.TimeoutExpired,RuntimeError,OSError) as q:
   log('reconcile_error',error=str(q)[-250:]);absent=False
  sleep(40)
  return None,absent
def pull(remote,name,required=True):
 p=O/name
 if not p.exists():
  try:cmd(LOCAL+['download','-s',NAME,remote,str(p)],240,required)
  except (RuntimeError,subprocess.TimeoutExpired,OSError) as e:
   if required:raise
   log('optional_pull_error',remote=remote,error=str(e)[-200:])
 if required:assert p.is_file() and p.stat().st_size>0
 return p
def verify_case(label,state):
 pair=[]
 for ext in ('thin.npz','points80.json'):
  key=f'{label}_{ext}.sha256';info=state['ready'][key];local=pull(f'/content/t5_out/{label}_{ext}',f'{label}_{ext}')
  assert local.stat().st_size==info['size'] and sha(local)==info['sha']
  assert pull(f'/content/t5_out/{key}',key).read_text().strip()==info['sha'];pair.append(info['sha'])
 points=json.loads((O/f'{label}_points80.json').read_text())
 assert points['label']==label and len(points['rows'])==80 and set(int(p['id']) for p in points['rows'])==set(range(1,81))
 for ext in ('solver.log','exit.json','actual_opencl.cl','ground_eligibility.csv','ground_excluded.csv','city_stability.csv','wall_tau_actual.csv'):
  pull(f'/content/t5_out/{label}_{ext}',f'{label}_{ext}',required=ext in ('solver.log','exit.json','actual_opencl.cl'))
 pairstr=' '.join(pair)
 try:reply=exec_file(R/'ack.py',{'T5_ACK_LABEL':label,'T5_ACK_PAIR':pairstr})
 except (subprocess.TimeoutExpired,RuntimeError) as e:
  log('ack_uncertain',label=label,error=str(e)[-250:]);reply=''
 if 'ACK '+label not in reply:assert label+'.ack' in probe_once()['ack'],'ACK unconfirmed'
 verified.add(label);log('host_verified',label=label,thin_sha256=pair[0],points_sha256=pair[1])
def stop(reason):
 assert reason in ('terminal_verified','deadline','endpoint_absent_3')
 log('stop_authorized',reason=reason,verified=sorted(verified))
 if reason!='endpoint_absent_3':
  for remote in ('/content/t5.log','/content/t5_out/run.done','/content/t5_out/run.failed','/content/t5_out/off_build.log','/content/t5_out/on_build.log'):
   pull(remote,pathlib.Path(remote).name,False)
  cmd(LOCAL+['stop','-s',NAME],150,False)
 view=cmd(BASE+['sessions'],100)[0];absent=ENDPOINT not in endpoints(view)
 log('stop_check',endpoint=ENDPOINT,endpoint_absent=absent,estimated_CU=(time.time()-created)*rate/3600 if created else None)
 orphan=cmd([str(pathlib.Path.home()/'bin/colab-orphans')],100,False)
 log('orphan_check',tail=orphan[0][-700:],rc=orphan[1]);assert absent,'owned endpoint still present; report platform'
 # The global list may include OTHER agents' orphans. Do not touch those assignments.
 if '孤儿=0' not in orphan[0]:log('foreign_orphan_warning',tail=orphan[0][-400:])
 cmd(['systemctl','--user','stop','colab-keepalive-'+NAME],30,False)
def main():
 global ENDPOINT,GPU,created,deadline,rate,launched
 assert sha(R/'stage_t5.tar.gz')==json.loads((R/'archive.json').read_text())['sha256']
 assert not CFG.exists() and not O.exists() and not EVENT.exists() and not (R/'.colab_owner').exists()
 before=endpoints(cmd(BASE+['sessions'])[0]);assert NAME not in cmd(BASE+['sessions'])[0]
 (R/'.colab_owner').open('x').write('delegation R21.4a-T5 researchos-uwind-luw\n');O.mkdir(exist_ok=False)
 for candidate in ('A100','G4'):
  try:text,rc=cmd(LOCAL+['new','-s',NAME,'--gpu',candidate],145,False)
  except subprocess.TimeoutExpired:raise RuntimeError('allocation ambiguous; reconcile before further action')
  if rc==0 and 'Session READY' in text:GPU=candidate;created=time.time();break
  if not re.search('503|412|Service Unavailable|Allocation refused|precondition failed',text,re.I):raise RuntimeError('ambiguous allocation '+text[-400:])
  assert NAME not in cmd(BASE+['sessions'])[0];log('allocation_refused',gpu=candidate)
 if not GPU:raise RuntimeError('A100 and G4 refused')
 diff=endpoints(cmd(BASE+['sessions'])[0])-before;assert len(diff)==1,'endpoint ambiguous';ENDPOINT=next(iter(diff))
 rate=5.4 if GPU=='A100' else 6.81
 deadline=created+(32/rate)*3600 # task cap 40 CU; prior G4 estimate 6.942 CU + 1 CU reserve
 log('allocated',gpu=GPU,endpoint=ENDPOINT,created=created,deadline=deadline,assumed_rate=rate)
 try:
  for name in ('stage_t5.tar.gz','archive.json','worker.py','launch.py','probe.py','ack.py','B2u_reference_points.json'):
   cmd(LOCAL+['upload','-s',NAME,str(R/name),'/content/'+name],180)
  parser=R.parent/'R21.4a_T3_emptyground/run2/remote_worker_run2.py'
  cmd(LOCAL+['upload','-s',NAME,str(parser),'/content/remote_worker_run2.py'],180)
  # Check actual target GPU's max allocation before creating a >100M-cell grid.
  gpu=exec_file(R/'gpu_probe.py',timeout=100);log('gpu_probe',tail=gpu[-650:])
  details=next((json.loads(x[4:]) for x in gpu.splitlines() if x.startswith('GPU ')),None)
  assert details and details['memory_free_mb']>=15000 and details['memory_total_mb']>=20000 and details['max_alloc_mb']>=9000,'insufficient GPU memory'
  if deadline-time.time()<5*3600 and GPU=='A100':raise RuntimeError('budget insufficient before launch')
  try:receipt=exec_file(R/'launch.py',{'T5_DEADLINE':str(deadline)},155)
  except (subprocess.TimeoutExpired,RuntimeError) as e:
   log('launch_uncertain',error=str(e));receipt=''
  if 'LAUNCHED' not in receipt:
   # The launch exec may have timed out after a successful state change.
   try:
    state=probe_once();assert state['log'] or state['ready'] or state['done'] or state['failed']
    log('launch_reconciled',tail=state['log'][-250:])
   except (subprocess.TimeoutExpired,RuntimeError,AssertionError,OSError,ValueError):
    raise RuntimeError('ambiguous launcher; retain owned session for reconciliation')
  launched=True
  log('launched',receipt=receipt[-180:])
  ka=[str(pathlib.Path.home()/'bin/colab-keepalive'),'--config',str(CFG),'-s',NAME,'--log','/content/t5.log','--proc','/content/worker.py','--until-marker','/content/t5_out/run.done','--stale-min','120','--max-hours','7','--expect-hours','6','--no-remind','--pull','/content/t5.log:'+str(O/'progress.log'),'--final-pull','/content/t5.log:'+str(O),'--detach']
  log('keepalive_start',receipt=cmd(ka,110)[0][-400:])
  absent_count=0
  while True:
   if time.time()>=deadline-240:stop('deadline');return False
   state,absent=monitor_once(probe_once,global_presence,time.sleep)
   if state is None:
    absent_count=absent_count+1 if absent else 0
    if absent_count>=3:stop('endpoint_absent_3');return False
    continue
   absent_count=0
   log('probe',ready=list(state['ready']),ack=state['ack'],done=state['done'],failed=state['failed'],tail=state['log'][-200:])
   for label in LABELS:
    keys=[f'{label}_{ext}.sha256' for ext in ('thin.npz','points80.json')]
    if all(k in state['ready'] for k in keys) and label not in verified:
     try:verify_case(label,state)
     except (subprocess.TimeoutExpired,RuntimeError,AssertionError,OSError,ValueError) as e:log('transfer_or_ack_error',label=label,error=str(e)[-450:])
   if state['done'] or state['failed']:
    available_verified=all(not any(k.startswith(label+'_') for k in state['ready']) or label in verified for label in LABELS)
    if available_verified and (state['failed'] or len(verified)==len(LABELS)):
     complete=state['done'] and not state['failed'] and len(verified)==len(LABELS)
     stop('terminal_verified');return complete
    log('terminal_waiting_for_evidence',verified=sorted(verified),ready=list(state['ready']))
   time.sleep(30)
 except BaseException as e:
  log('controller_error',error=str(e),traceback=traceback.format_exc()[-1300:])
  # No unconditional finally stop. Live endpoint is reconciled at return by operator.
  if not launched and GPU and ENDPOINT and 'ambiguous launcher' not in str(e):
   try:
    exec_file(R/'abort_prelaunch.py');state=probe_once()
    if state['failed'] and not state['ready']:stop('terminal_verified')
   except (subprocess.TimeoutExpired,RuntimeError,OSError,AssertionError,ValueError) as q:log('prelaunch_cleanup_uncertain',error=str(q)[-300:])
  if GPU and time.time()>=deadline-240:stop('deadline')
  return False
if __name__=='__main__':sys.exit(0 if main() else 2)
