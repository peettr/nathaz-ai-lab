#!/usr/bin/env python3
"""One-use run3 owner. Download and SHA-check each thin layer before ACK."""
from pathlib import Path
import subprocess,os,time,json,hashlib,re,sys,traceback
R=Path(__file__).resolve().parent;CFG=R/'sessions-run3.json';NAME='luw-r214a-t3r3-prod-1115';BASE=['colab','--auth','oauth2','--config',str(CFG)]
CASES=('dx1p0_s101','dx0p5_s101','dx1p0_s102','dx0p5_s102')
created=False;start=None;deadline=None;rate=6.81
EVENT=R/'controller_run3_events.jsonl';STATE=R/'controller_run3_state.json'
def event(kind,**kw):
 row={'event':kind,'time_epoch':time.time(),'session':NAME,'created_epoch':start,'deadline_epoch':deadline,'rate_assumed_CU_h':rate,**kw}
 with EVENT.open('a') as f:f.write(json.dumps(row)+'\n')
 STATE.write_text(json.dumps(row,indent=2)+'\n');print(kind,kw,flush=True)
def cmd(args,timeout=120,check=True):
 p=subprocess.run(args,capture_output=True,text=True,timeout=timeout,stdin=subprocess.DEVNULL)
 text=p.stdout+'\n'+p.stderr;text=re.sub(r'colab-runtime-proxy-token=[已隐去]','colab-runtime-proxy-token=[已隐去]',text)
 event('command',args=args,returncode=p.returncode,output=text[-600:])
 if check and p.returncode:raise RuntimeError('CLI failed '+str(args[-4:])+' '+text[-600:])
 return text
def cli(*a,timeout=120,check=True):return cmd(BASE+list(a),timeout,check)
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def download_case(case,sha,size):
 dest=R/f'{case}_thin.npz';receipt=R/f'{case}_thin.sha256'
 if dest.exists():
  assert digest(dest)==sha,'existing output hash disagrees; stop without overwrite'
 else:
  for attempt in range(3):
   temp=R/f'{case}_thin_download_attempt{attempt+1}.npz'
   if temp.exists():continue
   try:
    cli('download','-s',NAME,f'/content/t3_run3_out/{case}_thin.npz',str(temp),timeout=260)
    assert temp.stat().st_size==size and digest(temp)==sha,'download size/hash mismatch'
    temp.rename(dest);break
   except BaseException as e:event('thin_download_error',case=case,attempt=attempt+1,error=str(e)[-500:])
  assert dest.is_file() and digest(dest)==sha,'thin not verified'
 if not receipt.exists():receipt.write_text(sha+'\n')
 else:assert receipt.read_text().strip()==sha
 event('thin_verified_local',case=case,path=str(dest),size=dest.stat().st_size,sha256=sha)
 # Remote ACK is idempotently determined by the worker's exact SHA; no solver retry.
 ack=cli('exec','-s',NAME,'-f',str(R/'ack_run3.py'),'--env',f'T3_CASE={case}','--env',f'T3_SHA={sha}',timeout=100)
 assert 'ACK '+case in ack,ack[-500:]
 event('thin_acknowledged',case=case)
def main():
 global created,start,deadline
 view=cmd(['colab','--auth','oauth2','sessions'],timeout=60)
 assert NAME not in view,'session name taken'
 with (R/'.colab_owner_prod').open('x') as f:f.write('T3 run3 #current '+NAME+' '+str(time.time())+'\n')
 bundle=R.parent/'run2/stage_fixed_bundle.tar.gz';parser=R.parent/'run2/remote_worker_run2.py'
 man=json.loads((R.parent/'run2/stage_fixed/stage_manifest.json').read_text())
 for c,v in man['cases'].items():assert digest(R.parent/'run2/stage_fixed'/c/'conf.luwpf')==v['conf_sha256']
 start=time.time();event('allocation_begin')
 try:cli('new','-s',NAME,'--gpu','A100',timeout=130)
 except Exception as e:
  view=cmd(['colab','--auth','oauth2','sessions'],timeout=60)
  if NAME in view:raise RuntimeError('ambiguous A100 allocation; no fallback') from e
  if not re.search('503|412|Service Unavailable|Allocation refused',str(e),re.I):raise
  event('A100_refused_G4',error=str(e)[-350:]);start=time.time();cli('new','-s',NAME,'--gpu','G4',timeout=130)
 created=True;deadline=start+(55/rate)*3600
 probe=cli('exec','-s',NAME,'-f',str(R.parent/'run2/gpu_probe.py'),timeout=100)
 event('gpu_ready',probe=probe[-800:]);m=re.search(r'GPU\s+([^\n]+)',probe);assert m
 nums=re.findall(r'\b\d+\b',m.group(1));assert len(nums)>=2 and int(nums[-1])>29000,'insufficient GPU memory'
 host=re.search(r'MemAvailable:\s+(\d+)',probe);assert host and int(host.group(1))>24*1024*1024
 for local,remote in [(bundle,'/content/t3_run3_bundle.tar.gz'),(parser,'/content/t3_run2_parser.py'),(R/'remote_worker_run3.py','/content/t3_run3_worker.py')]:cli('upload','-s',NAME,str(local),remote,timeout=170)
 assert time.time()<deadline-600
 launch=cli('exec','-s',NAME,'-f',str(R/'launch_run3.py'),'--env',f'T3_DEADLINE={deadline}','--env',f'T3_BUNDLE_SHA={digest(bundle)}',timeout=150)
 event('launch_receipt',output=launch[-700:]);assert 'RUN3_LAUNCHED_PID' in launch,'ambiguous launch: inspect remote; no retry'
 keep=[str(Path.home()/'bin/colab-keepalive'),'--config',str(CFG),'-s',NAME,'--log','/content/t3_run3_stage/run3.log','--until-marker','/content/t3_run3_out/run.done','--pull','/content/t3_run3_stage/run3.log:'+str(R/'progress.log'),'--final-pull','/content/t3_run3_out/*_thin.sha256:'+str(R/'final_hashes'),'--expect-hours','8','--max-hours','9','--no-remind','--detach']
 event('keepalive_start',receipt=cmd(keep,timeout=115)[-500:])
 acked=set();misses=0
 while time.time()<deadline-350:
  try:status=cli('exec','-s',NAME,'-f',str(R/'check_run3.py'),timeout=110);misses=0
  except BaseException as e:
   misses+=1;event('probe_error',count=misses,error=str(e)[-350:]);
   if misses>=3:break
   time.sleep(40);continue
  for case,sz,sha in re.findall(r'THIN\s+(dx\S+_s\d+)_thin\.npz\s+(\d+)\s+([0-9a-f]{64})',status):
   if case not in acked:
    download_case(case,sha,int(sz));acked.add(case)
  if 'done True' in status or 'failed True' in status:break
  time.sleep(45)
 event('terminal',acked=sorted(acked),status=status[-900:])
 return len(acked)==4 and 'done True' in status
def stop():
 if not created:return
 for remote,dest in [('/content/t3_run3_stage/run3.log','remote_run3.log'),('/content/t3_run3_out/build.log','build.log'),('/content/t3_run3_out/run.failed','run.failed')]:
  p=R/dest
  if p.exists():continue
  try:cli('download','-s',NAME,remote,str(p),timeout=120)
  except BaseException as e:event('evidence_missing',path=remote,error=str(e)[-200:])
 for c in CASES:
  for ext in ('_solver.log','_exit.json','_thin_meta.json'):
   p=R/(c+ext)
   if not p.exists():
    try:cli('download','-s',NAME,'/content/t3_run3_out/'+c+ext,str(p),timeout=130)
    except BaseException as e:event('evidence_missing',path=c+ext,error=str(e)[-200:])
 try:cli('stop','-s',NAME,timeout=130);event('stop_called',CU_estimate=(time.time()-start)*rate/3600)
 except BaseException as e:event('stop_error',error=str(e)[-400:])
 try:
  view=cmd(['colab','--auth','oauth2','sessions'],timeout=60);event('stop_confirmed' if NAME not in view else 'stop_unconfirmed',CU_estimate=(time.time()-start)*rate/3600)
 except BaseException as e:event('stop_verify_error',error=str(e)[-300:])
 try:cmd(['systemctl','--user','stop','colab-keepalive-'+NAME],timeout=25,check=False)
 except BaseException:pass
if __name__=='__main__':
 try:ok=main();event('controller_finished',success=ok)
 except BaseException:event('controller_failed',trace=traceback.format_exc()[-2200:]);ok=False
 finally:stop()
 sys.exit(0 if ok else 2)
