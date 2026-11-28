#!/usr/bin/env python3.10
"""T7 two-case Colab controller, Linux scratch spool on ./ EIO."""
import pathlib,subprocess,json,time,hashlib,re,sys,traceback,os,shutil
R=pathlib.Path(__file__).resolve().parent
T=pathlib.Path(os.environ['TMPDIR'])/'luw-t7-buffer40-spool';T.mkdir(parents=True,exist_ok=True)
O=T/'evidence';O.mkdir(exist_ok=True);CFG=T/'sessions.json';EV=T/'events.jsonl'
NAME='luw-r214a-t7-buffer40-1117';LABELS=('E_s101_off','E_s102_off');BASE=['colab','--auth','oauth2'];C=BASE+['--config',str(CFG)]
endpoint=None;created=None;deadline=None;rate=None;verified=set();launched=False

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def sync():
 try:
  (R/'evidence').mkdir(exist_ok=True)
  for p in O.iterdir():
   dest=R/'evidence'/p.name
   if p.is_file() and not dest.exists():shutil.copy2(p,dest)
  shutil.copy2(EV,R/'events.jsonl')
 except OSError as e:print('MOUNT_SPOOL',str(e)[-180:],flush=True)
def log(ev,**kw):
 row={'time':time.strftime('%m-%d %H:%M:%S %Z'),'event':ev,**kw}
 with EV.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
 print(ev,kw,flush=True);sync()
def cmd(args,timeout=120,check=True):
 p=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
 log('command',argv=args[:7],rc=p.returncode,tail=p.stdout[-300:])
 if check and p.returncode:raise RuntimeError(p.stdout[-500:])
 return p.stdout,p.returncode
def endpoints(s):return set(re.findall(r'gpu-(?:a100|g4)-s-[a-z0-9-]+',s,re.I))
def execf(p,env=None,timeout=110):
 args=C+['exec','-s',NAME,'-f',str(p)]
 for k,v in (env or {}).items():args+=['--env',k+'='+str(v)]
 return cmd(args,timeout)[0]
def probe():
 text=execf(R/'probe.py');lines=[x for x in text.splitlines() if x.startswith('PROBE ')]
 if not lines:raise RuntimeError('missing PROBE '+text[-250:])
 return json.loads(lines[-1][6:])
def pull(remote,name,required=True):
 p=O/name
 if not p.exists():
  try:cmd(C+['download','-s',NAME,remote,str(p)],240,required)
  except (RuntimeError,subprocess.TimeoutExpired,OSError) as e:
   if required:raise
   log('optional_pull_error',name=name,error=str(e)[-180:])
 if required:assert p.is_file() and p.stat().st_size>0
 sync();return p
def verify(state,label):
 pair=[]
 for ext in ('thin.npz','points80.json'):
  key=f'{label}_{ext}.sha256';info=state['ready'][key]
  p=pull('/content/t7_out/'+label+'_'+ext,label+'_'+ext)
  assert sha(p)==info['sha'] and p.stat().st_size==info['size']
  assert pull('/content/t7_out/'+key,key).read_text().strip()==info['sha']
  pair.append(info['sha'])
 d=json.loads((O/(label+'_points80.json')).read_text());assert d['label']==label and len(d['rows'])==80 and set(int(x['id']) for x in d['rows'])==set(range(1,81))
 for ext in ('solver.log','exit.json','actual_opencl.cl','ground_eligibility.csv','ground_excluded.csv','city_stability.csv','wall_tau_actual.csv'):
  pull('/content/t7_out/'+label+'_'+ext,label+'_'+ext,ext in ('solver.log','exit.json','actual_opencl.cl'))
 cl=O/(label+'_actual_opencl.cl')
 match=re.search(r'^\s*#define def_buffer_N\s+(\d+)u',cl.read_text(),re.M)
 assert match and int(match.group(1))==40,'actual OpenCL buffer mismatch'
 try:reply=execf(R/'ack.py',{'T7_ACK_LABEL':label,'T7_ACK_PAIR':' '.join(pair)})
 except (RuntimeError,subprocess.TimeoutExpired) as e:log('ack_uncertain',error=str(e)[-180:]);reply=''
 if 'ACK '+label not in reply:assert label+'.ack' in probe()['ack']
 verified.add(label);log('host_verified',label=label,thin_sha256=pair[0],points_sha256=pair[1],actual_opencl_sha256=sha(cl),spool=str(O))
def stop(reason):
 assert reason in ('terminal_verified','deadline','endpoint_absent_3')
 log('stop_authorized',reason=reason,verified=sorted(verified))
 if reason!='endpoint_absent_3':
  for p in ('/content/t7.log','/content/t7_out/run.done','/content/t7_out/run.failed','/content/t7_out/off_build.log'):
   pull(p,pathlib.Path(p).name,False)
  cmd(C+['stop','-s',NAME],150,False)
 view=cmd(BASE+['sessions'],100)[0];absent=endpoint not in endpoints(view)
 log('stop_check',endpoint=endpoint,endpoint_absent=absent,estimated_CU=(time.time()-created)*rate/3600)
 orphans=cmd([str(pathlib.Path.home()/'bin/colab-orphans')],100,False)
 log('orphan_check',tail=orphans[0][-400:],rc=orphans[1]);assert absent,'owned endpoint remains, escalate platform'
 cmd(['systemctl','--user','stop','colab-keepalive-'+NAME],30,False)
 sync()
def main():
 global endpoint,created,deadline,rate,launched
 assert sha(R/'stage_t7.tar.gz')==json.loads((R/'archive.json').read_text())['sha256']
 assert not CFG.exists() and not (R/'.colab_owner').exists() and not (R/'evidence').exists()
 before=endpoints(cmd(BASE+['sessions'])[0]);assert NAME not in cmd(BASE+['sessions'])[0]
 (R/'.colab_owner').open('x').write('R21.4a-T7 researchos-uwind-luw '+time.strftime('%m-%d %H:%M %Z')+'\n')
 for gpu in ('G4','A100'):
  try:text,rc=cmd(C+['new','-s',NAME,'--gpu',gpu],145,False)
  except subprocess.TimeoutExpired:raise RuntimeError('allocation ambiguous, reconcile before retry')
  if rc==0 and 'Session READY' in text:created=time.time();break
  if not re.search('503|412|Service Unavailable|Allocation refused|precondition failed',text,re.I):raise RuntimeError('ambiguous allocation '+text[-400:])
  assert NAME not in cmd(BASE+['sessions'])[0];log('allocation_refused',gpu=gpu)
 else:raise RuntimeError('G4 and A100 allocation refused')
 diff=endpoints(cmd(BASE+['sessions'])[0])-before;assert len(diff)==1,diff
 endpoint=next(iter(diff));rate=5.4 if gpu=='A100' else 6.81;deadline=created+5.85/rate*3600
 log('allocated',gpu=gpu,endpoint=endpoint,created=created,deadline=deadline,assumed_rate=rate,cap_CU=6)
 try:
  for name in ('stage_t7.tar.gz','archive.json','worker.py','launch.py','probe.py','ack.py','B2u_reference_points.json'):
   cmd(C+['upload','-s',NAME,str(R/name),'/content/'+name],180)
  parser=R.parent/'R21.4a_T3_emptyground/run2/remote_worker_run2.py'
  cmd(C+['upload','-s',NAME,str(parser),'/content/remote_worker_run2.py'],180)
  g=execf(R/'gpu_probe.py',timeout=100)
  details=next((json.loads(x[4:]) for x in g.splitlines() if x.startswith('GPU ')),None)
  assert details and details['memory_free_mb']>=15000 and details['memory_total_mb']>=20000 and details['max_alloc_mb']>=9000
  # Measured prior one-case solve ~900 s; allow build, extraction, transfer and stop, plus variability.
  assert deadline-time.time()>2400,'insufficient residual budget before solver'
  try:reply=execf(R/'launch.py',{'T7_DEADLINE':str(deadline)},155)
  except (RuntimeError,subprocess.TimeoutExpired) as e:log('launch_uncertain',error=str(e)[-200:]);reply=''
  if 'LAUNCHED' not in reply:
   state=probe();assert state['log'] or state['ready'] or state['done'] or state['failed']
  launched=True;log('launched',receipt=reply[-180:])
  ka=[str(pathlib.Path.home()/'bin/colab-keepalive'),'--config',str(CFG),'-s',NAME,'--log','/content/t7.log','--proc','/content/worker.py','--until-marker','/content/t7_out/run.done','--stale-min','120','--max-hours','2','--expect-hours','1','--no-remind','--pull','/content/t7.log:'+str(O/'progress.log'),'--final-pull','/content/t7.log:'+str(O),'--detach']
  log('keepalive_start',receipt=cmd(ka,110)[0][-350:])
  absent_count=0
  while True:
   if time.time()>=deadline-120:stop('deadline');return False
   try:state=probe();absent_count=0
   except (subprocess.TimeoutExpired,RuntimeError,ValueError,OSError) as e:
    log('probe_error',error=str(e)[-200:])
    try:
     cmd(C+['status','-s',NAME],70,False)
     absent=endpoint not in endpoints(cmd(BASE+['sessions'],90)[0])
     absent_count=absent_count+1 if absent else 0
    except (subprocess.TimeoutExpired,RuntimeError,OSError) as q:log('reconcile_error',error=str(q)[-200:]);absent_count=0
    if absent_count>=3:stop('endpoint_absent_3');return False
    time.sleep(35);continue
   log('probe',ready=list(state['ready']),ack=state['ack'],done=state['done'],failed=state['failed'],tail=state['log'][-160:])
   for label in LABELS:
    keys=[label+'_'+x+'.sha256' for x in ('thin.npz','points80.json')]
    if all(k in state['ready'] for k in keys) and label not in verified:
     try:verify(state,label)
     except (subprocess.TimeoutExpired,RuntimeError,AssertionError,OSError,ValueError) as e:log('transfer_or_ack_error',label=label,error=str(e)[-250:])
   if state['done'] or state['failed']:
    if len(verified)==len(LABELS):
     stop('terminal_verified');return bool(state['done'] and not state['failed'])
    log('terminal_waiting_for_evidence',ready=list(state['ready']))
   time.sleep(25)
 except BaseException as e:
  log('controller_error',error=str(e),traceback=traceback.format_exc()[-900:])
  # Never stop merely on an ambiguous launcher/probe or host mount error.
  if not launched and endpoint and 'ambiguous' not in str(e):
   try:
    execf(R/'abort_prelaunch.py')
    if probe()['failed']:stop('terminal_verified')
   except Exception as q:log('prelaunch_cleanup_uncertain',error=str(q)[-200:])
  if endpoint and time.time()>=deadline-120:stop('deadline')
  return False
if __name__=='__main__':sys.exit(0 if main() else 2)
