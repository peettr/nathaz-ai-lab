#!/usr/bin/env python3.10
"""Owned Colab phase B controller. Probe errors are uncertain, never stop conditions."""
import pathlib,subprocess,json,time,os,hashlib,traceback,sys,re
R=pathlib.Path(__file__).resolve().parent; CFG=R/'sessions.json'; NAME='luw-r214a-t4-phaseb-v2-1116'; O=R/'evidence'; EVENT=R/'events.jsonl'
BASE=['colab','--auth','oauth2']; LOCAL=BASE+['--config',str(CFG)]
PREFIX=tuple('B_dx1p0_s'+str(i) for i in (107,108,109))
ENDPOINT=None; GPU=None; created=None; deadline=None; rate=None; verified=set(); last_state=None

def log(ev,**kw):
 row={'time':time.strftime('%m-%d %H:%M:%S %Z'),'event':ev,**kw}
 with EVENT.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
 print(ev,kw,flush=True)
def cmd(argv,timeout=120,check=True):
 p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout,stdin=subprocess.DEVNULL)
 text=p.stdout;log('command',argv=argv[:6],rc=p.returncode,tail=text[-450:])
 if check and p.returncode:raise RuntimeError('command failed '+str(argv[:6])+' '+text[-550:])
 return text,p.returncode
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def endpoints(text):return set(re.findall(r'gpu-(?:a100|g4)-s-[a-z0-9-]+',text,re.I))
def global_presence():
 text=cmd(BASE+['sessions'],timeout=75)[0]
 return ENDPOINT in endpoints(text),text
def exec_file(path,env=None,timeout=110):
 a=LOCAL+['exec','-s',NAME,'-f',str(path)]
 for k,v in (env or {}).items():a+=['--env',k+'='+str(v)]
 return cmd(a,timeout)[0]
def pull(label,suffix):
 dest=O/(label+'_'+suffix)
 if dest.exists():return dest
 cmd(LOCAL+['download','-s',NAME,'/content/phaseb_out/'+label+'_'+suffix,str(dest)],170)
 assert dest.is_file() and dest.stat().st_size>0
 return dest
def ack_case(label,info):
 expected=info['sha'];local=pull(label,'thin.npz')
 assert local.stat().st_size==info['size'] and sha(local)==expected
 assert pull(label,'thin.sha256').read_text().strip()==expected
 for name in ('thin_meta.json','exit.json','geometry_gate.csv','solver.log','ground_excluded.csv','ground_eligibility.csv','wall_tau_actual.csv','city_stability.csv','actual_opencl.cl'):pull(label,name)
 # The ACK script was staged and preflighted before the VM was created.
 try:reply=exec_file(R/'ack.py',{'ACK_LABEL':label,'ACK_SHA':expected})
 except (subprocess.TimeoutExpired,RuntimeError) as e:
  log('ack_uncertain',label=label,error=str(e)[-350:]);reply=''
 if 'ACK '+label not in reply:
  state=probe_once()
  assert label+'.ack' in state['ack'],'ACK state unconfirmed; keep session live'
 verified.add(label);log('host_verified',label=label,sha256=expected,path=str(local))
def probe_once():
 text=exec_file(R/'probe.py');line=next((x for x in text.splitlines() if x.startswith('PROBE ')),None)
 if not line:raise RuntimeError('probe missing '+text[-250:])
 return json.loads(line[6:])
def monitor_once(probe,global_check,sleep=lambda _:None):
 """Return (state, confirmed_absent); injected for actual timeout preflight."""
 try:return probe(),False
 except (subprocess.TimeoutExpired,RuntimeError,ValueError,OSError) as e:
  log('probe_error',error=str(e)[-350:]);
  try:
   # A timeout means unknown, not a dead worker. Query named status and global list.
   status=cmd(LOCAL+['status','-s',NAME],timeout=70,check=False)[0];log('named_status',tail=status[-300:])
   absent=not global_check()[0];log('global_reconcile',absent=absent)
  except (subprocess.TimeoutExpired,RuntimeError,OSError) as q:
   log('reconcile_error',error=str(q)[-300:]);absent=False
  sleep(40)
  return None,absent
def stop(reason):
 assert reason in ('terminal_verified','deadline','endpoint_absent_3'),reason
 log('stop_authorized',reason=reason,verified=sorted(verified))
 if reason!='endpoint_absent_3':
  for remote in ('/content/phaseb.log','/content/phaseb_out/run.failed','/content/phaseb_out/run.done'):
   dest=O/pathlib.Path(remote).name
   if not dest.exists():
    try:cmd(LOCAL+['download','-s',NAME,remote,str(dest)],110,False)
    except (subprocess.TimeoutExpired,RuntimeError,OSError) as e:log('final_pull_error',remote=remote,error=str(e)[-200:])
  cmd(LOCAL+['stop','-s',NAME],120,False)
 view=cmd(BASE+['sessions'],90)[0]
 log('stop_check',endpoint=ENDPOINT,endpoint_absent=ENDPOINT not in endpoints(view),sessions=view[-900:],estimated_new_CU=(time.time()-created)*rate/3600 if created else None)
 orphan=cmd([str(pathlib.Path.home()/'bin/colab-orphans')],90,False)
 log('orphan_check',result=orphan[0][-500:],rc=orphan[1])
 assert ENDPOINT not in endpoints(view) and orphan[1]==0 and '孤儿=0' in orphan[0]
 try:cmd(['systemctl','--user','stop','colab-keepalive-'+NAME],30,False)
 except (subprocess.TimeoutExpired,OSError) as e:log('keepalive_stop_error',error=str(e))
def main():
 global ENDPOINT,GPU,created,deadline,rate,last_state
 assert sha(R/'stage_phase.tar.gz')==json.loads((R/'archive.json').read_text())['sha256']
 assert not CFG.exists() and not EVENT.exists() and not O.exists() and not (R/'.colab_owner').exists()
 before=endpoints(cmd(BASE+['sessions'])[0]);assert NAME not in cmd(BASE+['sessions'])[0]
 (R/'.colab_owner').open('x').write('delegation R21.4a-T4 phaseB_v2 researchos-uwind-luw\n')
 O.mkdir(exist_ok=False);allocation_start=time.time()
 for n in range(13):
  for candidate in ('A100','G4'):
   try:text,rc=cmd(LOCAL+['new','-s',NAME,'--gpu',candidate],130,False)
   except subprocess.TimeoutExpired:
    log('allocation_ambiguous',gpu=candidate);raise RuntimeError('allocation timeout; reconcile manually, never duplicate')
   if rc==0 and 'Session READY' in text:GPU=candidate;created=time.time();break
   if not re.search('503|412|Service Unavailable|Allocation refused|precondition failed',text,re.I):raise RuntimeError('ambiguous allocation '+text[-500:])
   assert NAME not in cmd(BASE+['sessions'])[0];log('allocation_refused',attempt=n,gpu=candidate)
  if GPU:break
  if time.time()-allocation_start>=4*3600:raise RuntimeError('allocation 4h deadline')
  time.sleep(min(1200,max(0,allocation_start+4*3600-time.time())))
 assert GPU
 diff=endpoints(cmd(BASE+['sessions'])[0])-before
 assert len(diff)==1,'cannot establish owned endpoint';ENDPOINT=next(iter(diff))
 rate=6.81 if GPU=='G4' else 5.4
 # Historical estimate not reconciled to billing: reserve at most 10 CU for this VM; stop early.
 deadline=created+min(2.1,10/rate)*3600
 log('allocated',gpu=GPU,endpoint=ENDPOINT,created=created,deadline=deadline,assumed_rate=rate)
 if deadline-time.time()<3600:stop('deadline');return False
 try:
  gpu=exec_file(R.parent.parent/'R21.4a_T3_emptyground/run2/gpu_probe.py');log('gpu_probe',tail=gpu[-400:])
  for name in ('stage_phase.tar.gz','archive.json','worker.py','launch.py','probe.py','ack.py'):cmd(LOCAL+['upload','-s',NAME,str(R/name),'/content/'+name],160)
  parser=R.parent.parent/'R21.4a_T3_emptyground/run2/remote_worker_run2.py'
  cmd(LOCAL+['upload','-s',NAME,str(parser),'/content/remote_worker_run2.py'],160)
  try:launch=exec_file(R/'launch.py',{'PHASE_DEADLINE':str(deadline)},150)
  except (subprocess.TimeoutExpired,RuntimeError) as e:
   log('launch_uncertain',error=str(e));launch=''
  if 'LAUNCHED' not in launch:
   # Never repeat a state-changing launch after ambiguous timeout.
   log('launch_reconcile_required');raise RuntimeError('launch state ambiguous; retain live session')
  log('launched',receipt=launch[-200:])
  ka=[str(pathlib.Path.home()/'bin/colab-keepalive'),'--config',str(CFG),'-s',NAME,'--log','/content/phaseb.log','--proc','/content/worker.py','--until-marker','/content/phaseb_out/run.done','--stale-min','120','--max-hours','2.4','--expect-hours','2','--no-remind','--pull','/content/phaseb.log:'+str(O/'progress.log'),'--final-pull','/content/phaseb.log:'+str(O),'--detach']
  log('keepalive_start',receipt=cmd(ka,110)[0][-400:])
  absent_count=0
  while True:
   if time.time()>=deadline-180:
    log('deadline_reached');stop('deadline');return False
   state,absent=monitor_once(probe_once,global_presence,time.sleep)
   if state is None:
    absent_count=absent_count+1 if absent else 0
    if absent_count>=3:stop('endpoint_absent_3');return False
    continue
   absent_count=0;last_state=state
   log('probe',ready=list(state['ready']),ack=state['ack'],done=state['done'],failed=state['failed'],tail=state['log'][-250:])
   for label in PREFIX:
    key=label+'_thin.sha256'
    if key in state['ready'] and label not in verified:
     try:ack_case(label,state['ready'][key])
     except (subprocess.TimeoutExpired,RuntimeError,AssertionError,OSError) as e:log('transfer_or_ack_error',label=label,error=str(e)[-500:])
   if state['done'] or state['failed']:
    if all((label+'_thin.sha256' not in state['ready']) or label in verified for label in PREFIX):
     complete=state['done'] and len(verified)==len(PREFIX)
     stop('terminal_verified');return complete
   time.sleep(30)
 except BaseException as e:
  log('controller_error',error=str(e),traceback=traceback.format_exc()[-1600:])
  # Never stop in finally. Preserve ambiguous work until the absolute deadline.
  if GPU and time.time()>=deadline-180:stop('deadline')
  return False
if __name__=='__main__':sys.exit(0 if main() else 2)
