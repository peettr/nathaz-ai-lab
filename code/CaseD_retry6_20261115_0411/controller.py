#!/usr/bin/env python3
"""Single-owner Colab A100 Case D run with session-inclusive CU stop."""
from pathlib import Path
import hashlib,json,os,re,subprocess,time,zipfile,traceback
D=Path(__file__).resolve().parent;NAME='luw-c38-cased-r6-20261115';CFG=(D/'sessions_caseD.json').resolve();REMOTE='/content/luw-c38-cased-r6-20261115';LOG=D/'controller.log';STATE=D/'controller_state.json'
BASE=['colab','--auth','oauth2','--config',str(CFG)];created=False;start=None;rate=6.81;deadline=None

def stamp():return time.strftime('%Y-%m-%d %H:%M:%S %z')
def record(event,**kw):
 with LOG.open('a') as f:print(stamp(),event,json.dumps(kw,ensure_ascii=False),file=f,flush=True)
 STATE.write_text(json.dumps({'event':event,'timestamp':stamp(),'session':NAME,'session_created_before_epoch':start,'rate_CU_per_hour_conservative':rate,'deadline_epoch':deadline,**kw},indent=2))
def call(args,timeout=120,check=True):
 record('cli_call',args=[str(a) for a in args if not str(a).startswith('rcx1.')])
 p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 out=p.stdout+'\n'+p.stderr;safe=re.sub(r'colab-runtime-proxy-token=[已隐去]','colab-runtime-proxy-token=[已隐去]',out);record('cli_result',command=args[-3:],returncode=p.returncode,output=safe[-1400:])
 if check and p.returncode:raise RuntimeError(f'command failed: {args[-3:]} {safe[-700:]}')
 return out

def cli(*args,timeout=120,check=True):return call(BASE+list(args),timeout,check)
def localsha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def ensure_time(extra=90):
 assert deadline is not None and time.time()+extra<deadline,'creation-to-stop CU deadline reached'

def run():
 global created,start,rate,deadline
 # Account-wide view must precede ownership and new; private state alone hides other agents.
 view=call(['colab','--auth','oauth2','sessions']);assert NAME not in view,'name already assigned'
 owner=D/'.colab_owner'
 with owner.open('x') as f:f.write('R21.4 C38.2 Case D; researchos-uwind-luw; '+stamp()+'\n')
 start=time.time();record('creation_call_started')
 for gpu in ('A100','G4','L4','H100'):
  record('allocation_attempt',gpu=gpu)
  try: output=cli('new','-s',NAME,'--gpu',gpu,timeout=120)
  except RuntimeError as exc:
   if not any(token in str(exc) for token in ('Service Unavailable','Precondition Failed','Allocation refused')):raise
   view=call(['colab','--auth','oauth2','sessions']);assert NAME not in view,'ambiguous allocation: owned name appeared after refusal'
   record('allocation_refused',gpu=gpu,error=str(exc)[-500:]);continue
  created=True;rate=max(rate,{'A100':6.81,'H100':14.0,'G4':8.0,'L4':6.81}[gpu]);record('gpu_allocated',gpu=gpu,conservative_rate=rate);break
 else:raise RuntimeError('all authorized >=24GB GPU allocations refused')
 # Actual rate is printed by Colab new/status; allow a conservative historical floor.
 for pattern in (r'([\d.]+)\s*CU\s*/\s*(?:hr|h|hour)',r'([\d.]+)\s*compute units\s*/\s*(?:hr|h|hour)'):
  found=re.search(pattern,output,re.I)
  if found:rate=max(rate,float(found.group(1)))
 deadline=start+6.65/rate*3600
 record('session_created',new_output=output[-1200:])
 ensure_time(600)
 probe=cli('exec','-s',NAME,'-f',str(D/'gpu_probe.py'),timeout=90)
 assert 'MEMCHECK' in probe and 'FREE_G' in probe
 record('memory_probe_pass',detail=probe[-1200:])
 for local,remote in [(D/'cased_stage.tar.gz','/content/cased_stage.tar.gz'),(D/'remote_caseD.py','/content/remote_caseD.py'),(D/'verify_source.py','/content/verify_source.py')]:
  ensure_time(600);assert local.is_file(),local
  cli('upload','-s',NAME,str(local),remote,timeout=200)
 source=D.parent.parent/'caseA_r9_2m_tacc_v2/stage/source_dd438c1.tar.gz'
 assert localsha(source)=='88ac44d3005dde28267a18f40fe6d5f5071105719ead40ca12509a5c492204d0'
 parts=sorted((D/'source_parts').glob('part_*'))
 assert len(parts)>1 and sum(q.stat().st_size for q in parts)==source.stat().st_size
 for part in parts:
  ensure_time(600);assert part.stat().st_size<=10_000_000
  cli('upload','-s',NAME,str(part),'/content/'+part.name,timeout=120)
 ensure_time(600)
 transfer=cli('exec','-s',NAME,'-f',str(D/'verify_source.py'),timeout=180)
 assert 'SOURCE_VERIFIED' in transfer and localsha(source) in transfer,transfer
 record('source_verified',sha256=localsha(source),part_count=len(parts))
 record('uploads_done')
 ensure_time(2700)
 out=cli('exec','-s',NAME,'-f',str(D/'launch.py'),'--env',f'CASE_D_DEADLINE_EPOCH={deadline}',timeout=100)
 assert 'LAUNCHED' in out,out
 record('launched',launcher_output=out[-600:])
 # Mandatory detached keepalive; final pull is an independent fallback for result recovery.
 ka=call([str(Path.home()/'bin/colab-keepalive'),'--config',str(CFG),'-s',NAME,'--log',REMOTE+'/run.log','--until-marker',REMOTE+'/run.done','--pull',REMOTE+'/run.log:'+str(D/'remote_progress.log'),'--final-pull',REMOTE+'/result.zip:'+str(D),'--expect-hours','1.5','--max-hours','2','--no-remind','--detach'],timeout=100)
 record('keepalive_armed',receipt=ka[-1100:])
 while True:
  ensure_time(210)
  out=cli('exec','-s',NAME,'-f',str(D/'check.py'),timeout=90)
  record('progress',detail=out[-1600:])
  if 'STATUS' in out and 'done True' in out:
   m=re.search(r'RESULT_SHA256\s+([a-f0-9]{64})',out);assert m
   remote_sha=m.group(1)
   ensure_time(120)
   cli('download','-s',NAME,REMOTE+'/result.zip',str(D/'caseD_result.zip'),timeout=180)
   p=D/'caseD_result.zip';assert p.stat().st_size>0 and localsha(p)==remote_sha
   with zipfile.ZipFile(p) as z:
    assert not z.testzip();names=set(z.namelist());assert {'pointvalues.json','geometry_gate.json','solver_exit.json','sha256.json'}<=names
    pts=json.loads(z.read('pointvalues.json'));assert len(pts['rows'])==99 and all(len(q['c38_xyz_m'])==3 for q in pts['rows'])
    assert json.loads(z.read('solver_exit.json'))['exit']==0
   record('verified',result_path=str(p),sha256=remote_sha,npoints=99,elapsed_session_s=time.time()-start,CU_estimate=(time.time()-start)*rate/3600)
   return
  if 'STATUS' in out and 'failed True' in out:raise RuntimeError(out[-1500:])
  time.sleep(30)
try:run()
except BaseException as ex:record('failed',error=str(ex)[-3000:],trace=traceback.format_exc()[-3000:])
finally:
 if created:
  # Preserve failure logs if no final result before releasing the owned VM.
  if not (D/'caseD_result.zip').exists():
   for name in ('run.log','run.failed','gate_solver.log','solver.log','build.log'):
    try:cli('download','-s',NAME,REMOTE+'/'+name,str(D/('remote_'+name)),timeout=70)
    except BaseException as ex:record('download_unavailable',name=name,error=str(ex)[-200:])
  try:cli('stop','-s',NAME,timeout=100)
  except BaseException as ex:record('STOP_FAILED',error=str(ex)[-500:])
  else:
   try:record('session_stopped',sessions=call(['colab','--auth','oauth2','sessions'])[-900:],elapsed_session_s=time.time()-start,CU_estimate=(time.time()-start)*rate/3600)
   except BaseException as ex:record('stop_confirm_error',error=str(ex)[-500:])
 else:record('no_session_created')
