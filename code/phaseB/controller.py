#!/usr/bin/env python3
"""Host orchestration and byte verification; never computes solver on host."""
import pathlib,subprocess,json,time,os,hashlib,traceback,sys,re
R=pathlib.Path(__file__).resolve().parent;CFG=R/'sessions.json';NAME='luw-r214a-t4-phaseb-v2-1116';O=R/'evidence';O.mkdir(exist_ok=False)
EVENT=R/'events.jsonl';BASE=['colab','--auth','oauth2'];LOCAL=BASE+['--config',str(CFG)];GPU=None;ENDPOINT=None;created=None;FAILURE=False
PREFIX=('B_dx1p0_s107','B_dx1p0_s108','B_dx1p0_s109')
def log(ev,**kw):
 with EVENT.open('a') as f:f.write(json.dumps({'time':time.strftime('%m-%d %H:%M:%S %Z'),'event':ev,**kw})+'\n')
def cmd(argv,timeout=90,check=True):
 p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
 text=p.stdout;log('command',argv=argv[:6],rc=p.returncode,tail=text[-550:])
 if check and p.returncode:raise RuntimeError('command failed '+str(argv[:6])+' '+text[-800:])
 return text,p.returncode
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def endpoints(text):return set(re.findall(r'gpu-(?:a100|g4)-s-[a-z0-9-]+',text,re.I))
def pull(label,remote_name):
 dest=O/(label+'_'+remote_name)
 assert not dest.exists();cmd(LOCAL+['download','-s',NAME,f'/content/phaseb_out/{label}_{remote_name}',str(dest)],120)
 assert dest.exists() and dest.stat().st_size>0
 return dest
def exec_file(path,env=None):
 a=LOCAL+['exec','-s',NAME,'-f',str(path)]
 for k,v in (env or {}).items():a+=['--env',k+'='+str(v)]
 return cmd(a,110)[0]
try:
 assert sha(R/'stage_phase.tar.gz')==json.loads((R/'archive.json').read_text())['sha256']
 assert not CFG.exists() and not EVENT.exists()
 before_text=cmd(BASE+['sessions'])[0];before=endpoints(before_text)
 assert NAME not in before_text
 assert not (R/'.colab_owner').exists();(R/'.colab_owner').write_text('delegation c47882a5 phaseB researchos-uwind-luw\n')
 start=time.time()
 for round_no in range(13):
  for candidate in ('A100','G4'):
   text,rc=cmd(LOCAL+['new','-s',NAME,'--gpu',candidate],100,False)
   if rc==0 and 'Session READY' in text:
    GPU=candidate;created=time.time();break
   if '503' not in text and 'Service Unavailable' not in text and 'Allocation refused' not in text and 'precondition failed' not in text:raise RuntimeError('ambiguous allocation: '+text[-800:])
   assert NAME not in cmd(BASE+['sessions'])[0]
   log('allocation_refused',round=round_no,gpu=candidate)
  if GPU:break
  if time.time()-start>=4*3600:raise RuntimeError('allocation timeout')
  time.sleep(min(1200,max(0,start+4*3600-time.time())))
 assert GPU
 current=cmd(BASE+['sessions'])[0];diff=endpoints(current)-before
 if len(diff)==1:ENDPOINT=next(iter(diff))
 log('allocated',gpu=GPU,endpoint=ENDPOINT,created=created)
 # hard upper limit for this new session, leaving historic unknown CU unclaimed
 rate=6.81 if GPU=='G4' else 5.4
 deadline=created+min(2.2,10/rate)*3600
 if deadline-time.time()<3600:raise RuntimeError('insufficient budget after allocation')
 probe=exec_file(R.parent.parent/'R21.4a_T3_emptyground/run2/gpu_probe.py')
 log('gpu_probe',text=probe[-600:])
 for source,target in [('stage_phase.tar.gz','stage_phase.tar.gz'),('archive.json','archive.json'),('worker.py','worker.py'),('launch.py','launch.py'),('probe.py','probe.py')]:cmd(LOCAL+['upload','-s',NAME,str(R/source),'/content/'+target],120)
 parser=R.parent.parent/'R21.4a_T3_emptyground/run2/remote_worker_run2.py'
 cmd(LOCAL+['upload','-s',NAME,str(parser),'/content/remote_worker_run2.py'],120)
 launch=exec_file(R/'launch.py',{'PHASE_DEADLINE':str(deadline)})
 assert 'LAUNCHED' in launch,launch
 log('launched',receipt=launch[-200:])
 ka=['./bin/colab-keepalive','--config',str(CFG),'-s',NAME,'--log','/content/phaseb.log','--proc','/content/worker.py','--until-marker','/content/phaseb_out/run.done','--stale-min','120','--max-hours','2.4','--expect-hours','2','--no-remind','--final-pull','/content/phaseb.log:'+str(O),'--final-pull','/content/phaseb_out/run.failed:'+str(O),'--detach']
 cmd(ka,80);log('keepalive_started')
 processed=set();complete=False
 while time.time()<deadline-180:
  probe=exec_file(R/'probe.py');line=next((x for x in probe.splitlines() if x.startswith('PROBE ')),None)
  if not line:raise RuntimeError('probe missing '+probe[-300:])
  state=json.loads(line[6:]);log('probe',ready=list(state['ready']),tail=state['log'][-250:],failed=state['failed'])
  for label in PREFIX:
   key=label+'_thin.sha256'
   if key not in state['ready'] or label in processed:continue
   local=pull(label,'thin.npz');expected=state['ready'][key]['sha'];assert local.stat().st_size==state['ready'][key]['size'] and sha(local)==expected
   sha_file=pull(label,'thin.sha256');assert sha_file.read_text().strip()==expected
   pull(label,'thin_meta.json');pull(label,'exit.json');pull(label,'geometry_gate.csv');pull(label,'solver.log')
   if label.startswith('B_'):
    for name in ('ground_excluded.csv','ground_eligibility.csv','wall_tau_actual.csv','city_stability.csv','actual_opencl.cl'):pull(label,name)
   verdict=True
   # Return only a short ACK; files must have been verified locally first.
   a=R/'ack.py';a.write_text("import pathlib,json,os\nr=pathlib.Path('/content/phaseb_out')\nk=os.environ['ACK_LABEL'];v=os.environ['ACK_SHA'];p=r/(k+'_thin.sha256')\nassert p.read_text().strip()==v\n(r/(k+'.ack')).write_text(v)\nif k.startswith('A_'):(r/'A_verdict.json').write_text(os.environ['A_VERDICT'])\nprint('ACK',k)\n")
   exec_file(a,{'ACK_LABEL':label,'ACK_SHA':expected,'A_VERDICT':json.dumps({'bitwise_equal':bool(verdict)})})
   processed.add(label);log('host_verified',label=label,sha=expected,bitwise_equal=verdict)
  if complete or state['done'] or state['failed'] or state['stopped_A']:break
  time.sleep(25)
 if state['failed']:raise RuntimeError('remote worker failed '+state['log'][-400:])
 if len(processed)==len(PREFIX) and state['done']:complete=True
 if not complete:raise RuntimeError('incomplete '+str(sorted(processed)))
except BaseException as e:
 FAILURE=True
 log('error',error=str(e),traceback=traceback.format_exc()[-2400:]);print('ERROR',e,flush=True)
finally:
 if GPU:
  # Preserve compact evidence, then stop only this owned named session.
  try:
   for remote in ('/content/phaseb.log','/content/phaseb_out/run.failed','/content/phaseb_out/run.done','/content/phaseb_out/run.stopped_A'):
    dest=O/pathlib.Path(remote).name
    if not dest.exists():cmd(LOCAL+['download','-s',NAME,remote,str(dest)],90,False)
   cmd(LOCAL+['stop','-s',NAME],90,False)
   after=cmd(BASE+['sessions'])[0];log('stop_check',endpoint=ENDPOINT,endpoint_absent=bool(ENDPOINT and ENDPOINT not in after),sessions=after[-1200:])
   if not ENDPOINT or ENDPOINT in after:FAILURE=True
   orphan=subprocess.run(['./bin/colab-orphans'],capture_output=True,text=True,timeout=80);log('orphan_check',output=orphan.stdout[-500:],rc=orphan.returncode)
   if orphan.returncode or '孤儿=0' not in orphan.stdout:FAILURE=True
  except BaseException as e:FAILURE=True;log('stop_error',error=str(e))
print('FINISHED',{'processed':list(processed),'endpoint':ENDPOINT,'gpu':GPU},flush=True)
if FAILURE:sys.exit(2)
