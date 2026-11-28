#!/usr/bin/env python3
"""One-shot bounded Colab main-path smoke; continuation requires real gates."""
from pathlib import Path
import hashlib,json,os,re,subprocess,time,traceback,sys
BASE=Path(__file__).resolve().parent
SRC=BASE.parent
NAME='luw-t4-try13-main-smoke-1116'
CFG=BASE/'sessions.json'
CMD=['colab','--auth','oauth2','--config',str(CFG)]
start=None;gpu=None;created=False
E=BASE/'events.jsonl'
def record(kind,**kw):
 row={'time':time.strftime('%m-%d %H:%M:%S %Z'),'event':kind,**kw}
 with E.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
 print(json.dumps(row,ensure_ascii=False),flush=True)
def call(args,timeout=120,check=True):
 p=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=timeout)
 text=p.stdout+'\n'+p.stderr
 text=re.sub(r'colab-runtime-proxy-token=[已隐去]','colab-runtime-proxy-token=[已隐去]',text)
 record('command',argv=args[:6],rc=p.returncode,tail=text[-250:])
 if check and p.returncode:raise RuntimeError(text[-400:])
 return text
def cli(*args,**kw):return call(CMD+list(args),**kw)
def sessions():return call(['colab','--auth','oauth2','sessions'],timeout=70)
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 global created,start,gpu
 assert not E.exists() and NAME not in sessions()
 with (BASE/'.colab_owner').open('x') as f:f.write('#c47882a5 '+NAME+' '+time.strftime('%m-%d %H:%M %Z')+'\n')
 m=json.loads((SRC/'try13_main_archive.json').read_text())
 assert sha(SRC/'try13_main_stage.tar.gz')==m['archive_sha256']
 for n,d in m['source_sha256'].items():assert sha(SRC/'main_stage/FluidX3D_on/src'/n)==d
 record('precheck_pass',archive_sha=m['archive_sha256'])
 allocation=time.monotonic();round_=0
 while time.monotonic()-allocation<4*3600 and not created:
  round_+=1
  for shape in ('A100','G4'):
   record('allocation_attempt',round=round_,gpu=shape)
   try:
    cli('new','-s',NAME,'--gpu',shape,timeout=160)
    created=True;start=time.time();gpu=shape
    record('allocated',gpu=gpu,start=start)
    break
   except Exception as exc:
    if NAME in sessions():created=True;start=time.time();raise RuntimeError('ambiguous live allocation; no fallback') from exc
    if isinstance(exc,subprocess.TimeoutExpired) or not re.search(r'503|412|Service Unavailable|Allocation refused',str(exc),re.I):raise
    record('allocation_refused',round=round_,gpu=shape,error=str(exc)[-200:])
  if not created:
   delay=max(0,min(allocation+round_*1200-time.monotonic(),4*3600-(time.monotonic()-allocation)))
   record('backoff_seconds',duration=round(delay));time.sleep(delay)
 if not created:raise RuntimeError('allocation exhausted 4h')
 for local,remote in ((SRC/'try13_main_stage.tar.gz','/content/try13_main_stage.tar.gz'),(SRC/'try13_main_archive.json','/content/try13_main_archive.json'),(SRC/'main_smoke_worker.py','/content/try13_main_smoke_worker.py')):
  cli('upload','-s',NAME,str(local),remote,timeout=180)
 try:response=cli('exec','-s',NAME,'-f',str(SRC/'main_smoke_launch.py'),timeout=120)
 except Exception:
  # Ambiguous launch is not retried. Preserve VM for read-only diagnosis.
  record('launch_ambiguous');raise
 assert 'MAIN_SMOKE_PID' in response,response[-300:]
 ka=[str(Path.home()/'bin/colab-keepalive'),'--config',str(CFG),'-s',NAME,'--log','/content/try13_main_smoke.log','--proc','/content/try13_main_smoke_worker.py','--stale-min','180','--until-marker','/content/try13_main_smoke/run.done','--final-pull','/content/try13_main_smoke/*.json:'+str(BASE/'final'),'--final-pull','/content/try13_main_smoke/*.csv:'+str(BASE/'final'),'--final-pull','/content/try13_main_smoke/*.log:'+str(BASE/'final'),'--final-pull','/content/try13_main_smoke/*.cl:'+str(BASE/'final'),'--max-hours','3','--expect-hours','2','--detach']
 call(ka,timeout=120)
 record('keepalive_started')
 deadline=start+(2*3600 if gpu=='A100' else 3*3600)
 while time.time()<deadline-600:
  time.sleep(45)
  status=Path.home()/'platform/colab-keepalive'/f'{NAME}.json'
  if status.exists():
   d=json.loads(status.read_text())
   if d.get('state')=='done' and d.get('final_pull_state')=='ok':break
   if d.get('state') not in (None,'running','done'):raise RuntimeError('keepalive: '+str(d.get('state')))
  if (BASE/'final/run.failed').exists():raise RuntimeError('worker failed')
 else:raise RuntimeError('CU deadline exceeded')
 p=BASE/'final/gate.json';assert p.exists() and p.stat().st_size>100
 g=json.loads(p.read_text());cl=BASE/'final/actual_opencl.cl'
 assert cl.exists() and sha(cl)==g['actual_opencl_sha256']
 assert g['solver_exit']==0 and g['valid_tau_columns']>0
 record('smoke_verified',gate=g,cl_sha256=sha(cl))
def stop():
 if not created:return
 try:
  if NAME in sessions():
   # Preserve remote diagnostics even when the terminal marker is absent.
   for remote,local in (('/content/try13_main_smoke.log','worker.log'),('/content/try13_main_smoke/run.failed','worker.failed')):
    if not (BASE/local).exists():
     try:cli('download','-s',NAME,remote,str(BASE/local),timeout=120)
     except Exception as exc:record('optional_pull_failed',remote=remote,error=str(exc)[-160:])
   cli('stop','-s',NAME,timeout=150)
  record('stop_confirmed',absent=NAME not in sessions(),elapsed_h=(time.time()-start)/3600,gpu=gpu)
 except Exception as exc:record('stop_failed',error=str(exc)[-300:])
if __name__=='__main__':
 code=0
 try:main()
 except BaseException:record('controller_failed',trace=traceback.format_exc()[-1800:]);code=2
 finally:stop()
 sys.exit(code)
