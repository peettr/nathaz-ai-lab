#!/usr/bin/env python3
"""Single-owner Colab A100 BG_1H run with session-inclusive CU stop."""
from pathlib import Path
import hashlib,json,os,re,subprocess,time,zipfile,traceback
D=Path(__file__).resolve().parent;NAME='luw-c38-bg1h-v4-20261115_1050';CFG=(D/'sessions_BG_1H.json').resolve();REMOTE='/content/luw-c38-bg1h-v4-20261115_1050';LOG=D/'controller.log';STATE=D/'controller_state.json'
BASE=['colab','--auth','oauth2','--config',str(CFG)];created=False;start=None;rate=6.81;deadline=None;gpu_selected=None

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

def probe_launch():
 """Read-only remote probe after an ambiguous launch; never resubmit the launcher."""
 for attempt in range(3):
  ensure_time(240)
  try:
   out=cli('exec','-s',NAME,'-f',str(D/'check.py'),timeout=90)
   record('launch_probe',attempt=attempt,detail=out[-1600:])
   if 'STARTED True' in out or 'done True' in out or 'failed True' in out:
    return True
   if 'STARTED False' in out and 'PROCESSES []' in out:
    # A read-only confirmation, not an inference from the timed-out client.
    if attempt==2: return False
  except BaseException as ex:record('launch_probe_error',attempt=attempt,error=str(ex)[-500:])
  time.sleep(15)
 raise RuntimeError('launch status ambiguous after read-only probes; no relaunch')

def run():
 global created,start,rate,deadline,gpu_selected
 # Account-wide view must precede ownership and new; private state alone hides other agents.
 view=call(['colab','--auth','oauth2','sessions']);assert NAME not in view,'name already assigned'
 owner=D/'.colab_owner'
 with owner.open('x') as f:f.write('R21.4 C38.2 BG_1H; researchos-uwind-luw; '+stamp()+'\n')
 start=time.time();record('creation_call_started')
 for gpu in ('A100','G4','L4'):
  record('allocation_attempt',gpu=gpu)
  try: output=cli('new','-s',NAME,'--gpu',gpu,timeout=120)
  except RuntimeError as exc:
   if not any(token in str(exc) for token in ('Service Unavailable','Precondition Failed','Allocation refused','Backend rejected accelerator')):raise
   view=call(['colab','--auth','oauth2','sessions']);assert NAME not in view,'ambiguous allocation: owned name appeared after refusal'
   record('allocation_refused',gpu=gpu,error=str(exc)[-500:]);continue
  created=True;gpu_selected=gpu;rate=max(rate,{'A100':6.81,'H100':14.0,'G4':8.0,'L4':6.81}[gpu]);record('gpu_allocated',gpu=gpu,conservative_rate=rate);break
 else:raise RuntimeError('all authorized >=24GB GPU allocations refused')
 # Actual rate is printed by Colab new/status; allow a conservative historical floor.
 for pattern in (r'([\d.]+)\s*CU\s*/\s*(?:hr|h|hour)',r'([\d.]+)\s*compute units\s*/\s*(?:hr|h|hour)'):
  found=re.search(pattern,output,re.I)
  if found:rate=max(rate,float(found.group(1)))
 deadline=start+1.96/rate*3600
 record('session_created',new_output=output[-1200:])
 ensure_time(300)
 probe=cli('exec','-s',NAME,'-f',str(D/'gpu_probe.py'),timeout=90)
 assert 'MEMCHECK' in probe and 'FREE_G' in probe
 record('memory_probe_pass',gpu=gpu_selected,detail=probe[-1200:])
 for local,remote in [(D/'bg_stage.tar.gz','/content/bg_stage.tar.gz'),(D/'remote_BG.py','/content/remote_BG.py'),(D/'verify_source.py','/content/verify_source.py'),(D/'diagnostic_extract.py','/content/diagnostic_extract.py'),(D/'v4_alignment.py','/content/v4_alignment.py')]:
  ensure_time(300);assert local.is_file(),local
  cli('upload','-s',NAME,str(local),remote,timeout=200)
 # Verify the exact script on the VM before launching, not merely the local revision.
 check_diag=cli('exec','-s',NAME,'-f',str(D/'verify_diagnostic_upload.py'),timeout=90)
 assert 'DIAGNOSTIC_SHA256 '+localsha(D/'diagnostic_extract.py') in check_diag,check_diag[-600:]
 record('remote_diagnostic_verified',sha256=localsha(D/'diagnostic_extract.py'))
 source=D.parent.parent/'caseA_r9_2m_tacc_v2/stage/source_dd438c1.tar.gz'
 assert localsha(source)=='88ac44d3005dde28267a18f40fe6d5f5071105719ead40ca12509a5c492204d0'
 parts=sorted((D.parent/'CaseD_retry9_20261115_0756'/'source_parts').glob('part_*'))
 assert len(parts)>1 and sum(q.stat().st_size for q in parts)==source.stat().st_size
 for part in parts:
  ensure_time(300);assert part.stat().st_size<=10_000_000
  cli('upload','-s',NAME,str(part),'/content/'+part.name,timeout=120)
 ensure_time(300)
 transfer=cli('exec','-s',NAME,'-f',str(D/'verify_source.py'),timeout=180)
 assert 'SOURCE_VERIFIED' in transfer and localsha(source) in transfer,transfer
 record('source_verified',sha256=localsha(source),part_count=len(parts))
 record('uploads_done')
 ensure_time(300)
 try:
  out=cli('exec','-s',NAME,'-f',str(D/'launch.py'),'--env',f'BG_DEADLINE_EPOCH={deadline}',timeout=100)
  record('launch_cli_returned',launcher_output=out[-600:])
 except subprocess.TimeoutExpired as ex:
  record('launch_exec_timeout_ambiguous',error=str(ex)[-600:])
  out=''
 # Do not infer remote failure from a client timeout. Arm mandatory keepalive
 # before read-only probes; its own kernel activity protects a live solver.
 ka=call([str(Path.home()/'bin/colab-keepalive'),'--config',str(CFG),'-s',NAME,'--log',REMOTE+'/run.log','--until-marker',REMOTE+'/run.done','--pull',REMOTE+'/run.log:'+str(D/'remote_progress.log'),'--final-pull',REMOTE+'/result.zip:'+str(D/'final_pull'),'--expect-hours','0.5','--max-hours','1','--no-remind','--detach'],timeout=100)
 record('keepalive_armed',receipt=ka[-1100:])
 if not probe_launch():raise RuntimeError('confirmed not started: no remote marker, process or log on three probes')
 record('launch_confirmed_by_remote_probe')
 while True:
  ensure_time(210)
  out=cli('exec','-s',NAME,'-f',str(D/'check.py'),timeout=90)
  record('progress',detail=out[-1600:])
  if 'STATUS' in out and 'done True' in out:
   m=re.search(r'RESULT_SHA256\s+([a-f0-9]{64})',out);assert m
   remote_sha=m.group(1)
   ensure_time(120)
   cli('download','-s',NAME,REMOTE+'/result.zip',str(D/'BG_1H_v4_result.zip'),timeout=180)
   p=D/'BG_1H_v4_result.zip';assert p.stat().st_size>0 and localsha(p)==remote_sha
   with zipfile.ZipFile(p) as z:
    assert not z.testzip();names=set(z.namelist());assert {'pointvalues.json','geometry_gate.json','iou_registration.json','solver_exit.json','sha256.json','profiles_upstream.json','profiles_open_streets.json','vtk_header_sha256.json'}<=names
    pts=json.loads(z.read('pointvalues.json'));assert len(pts['rows'])==195 and all(len(q['c38_xyz_m'])==3 for q in pts['rows'])
    assert json.loads(z.read('solver_exit.json'))['exit']==0
    assert pts['selected_offset_xy_m']==[2,2] and len(pts['offset_0_2_rows'])==len(pts['rows'])
    ledger=json.loads(z.read('sha256.json'))
    assert all(hashlib.sha256(z.read(n)).hexdigest()==v for n,v in ledger.items())
   record('verified',gpu=gpu_selected,result_path=str(p),sha256=remote_sha,npoints=195,elapsed_session_s=time.time()-start,CU_estimate=(time.time()-start)*rate/3600)
   return
  if 'STATUS' in out and 'failed True' in out:raise RuntimeError(out[-1500:])
  time.sleep(30)
try:run()
except BaseException as ex:record('failed',error=str(ex)[-3000:],trace=traceback.format_exc()[-3000:]);raise
finally:
 if created:
  # Preserve failure logs if no final result before releasing the owned VM.
  if not (D/'BG_1H_v4_result.zip').exists():
   for name in ('run.log','run.failed','gate_solver.log','solver.log','build.log'):
    try:cli('download','-s',NAME,REMOTE+'/'+name,str(D/('remote_'+name)),timeout=70)
    except BaseException as ex:record('download_unavailable',name=name,error=str(ex)[-200:])
  try:cli('stop','-s',NAME,timeout=100)
  except BaseException as ex:record('STOP_FAILED',error=str(ex)[-500:])
  else:
   try:record('session_stopped',gpu=gpu_selected,sessions=call(['colab','--auth','oauth2','sessions'])[-900:],elapsed_session_s=time.time()-start,CU_estimate=(time.time()-start)*rate/3600)
   except BaseException as ex:record('stop_confirm_error',error=str(ex)[-500:])
 else:record('no_session_created')
