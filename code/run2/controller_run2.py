#!/usr/bin/env python3
"""Single-owner metered Colab controller; never restart a solver after ambiguity."""
from pathlib import Path
import subprocess,os,time,json,hashlib,re,sys,zipfile,traceback
R=Path(__file__).resolve().parent; CFG=R/'sessions-run2.json'; NAME='luw-r214a-t3r2-prod-1115'; BASE=['colab','--auth','oauth2','--config',str(CFG)]
created=False; start=None; rate=6.81; deadline=None
STATE=R/'controller_run2_state.json'; RECORD=R/'controller_run2_events.jsonl'
def event(kind,**kw):
 row={'time_epoch':time.time(),'event':kind,'session':NAME,'created_epoch':start,'rate_assumed_CU_h':rate,'deadline_epoch':deadline,**kw}
 with RECORD.open('a') as f:f.write(json.dumps(row)+'\n')
 STATE.write_text(json.dumps(row,indent=2)+'\n');print(kind,kw,flush=True)
def cmd(a,timeout=120,check=True):
 p=subprocess.run(a,capture_output=True,text=True,timeout=timeout,stdin=subprocess.DEVNULL)
 output=p.stdout+'\n'+p.stderr
 output=re.sub(r'colab-runtime-proxy-token=[已隐去]','colab-runtime-proxy-token=[已隐去]',output)
 event('command',args=[str(x) for x in a if not str(x).startswith('rcx1.')],returncode=p.returncode,output=output[-1100:])
 if check and p.returncode:raise RuntimeError(f'CLI failed {a[-4:]}: {output[-700:]}')
 return output
 def_nothing=None

def cli(*a,timeout=120,check=True):return cmd(BASE+list(a),timeout,check)
def hashfile(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()
def safe_deadline(reserve_s=120):
 if start and time.time()+reserve_s>=deadline:raise RuntimeError('session-inclusive 60-CU stop deadline reached')
def verify_zip(p):
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None
  mn=[n for n in z.namelist() if n.endswith('_manifest.json')];assert len(mn)==1
  d=json.loads(z.read(mn[0]));assert all(hashlib.sha256(z.read(n)).hexdigest()==v['sha256'] and len(z.read(n))==v['size'] for n,v in d.items())
  metric=[n for n in z.namelist() if n.endswith('_metrics.json')];assert len(metric)==1
  obj=json.loads(z.read(metric[0]));assert len(obj['G_curve'])>=15 and len(obj['vertical_at_xc'])==41
 return obj
def probe():
 return cli('exec','-s',NAME,'-f',str(R/'check_run2.py'),timeout=100)
def download_results():
 results={}
 for case in ('dx1p0_s101','dx0p5_s101','dx1p0_s102','dx0p5_s102'):
  p=R/f'{case}_run2.zip'
  if p.exists():results[case]=verify_zip(p);continue
  try:
   cli('download','-s',NAME,f'/content/t3_run2_out/{case}.zip',str(p),timeout=150)
   results[case]=verify_zip(p);event('verified_result',case=case,sha256=hashfile(p),metric_sha=hashlib.sha256(json.dumps(results[case],sort_keys=True).encode()).hexdigest())
  except BaseException as exc:event('result_pending_or_failed',case=case,error=str(exc)[-350:])
 return results
def main():
 global created,start,rate,deadline
 view=cmd(['colab','--auth','oauth2','sessions'],timeout=50);assert NAME not in view,'session name already taken'
 owner=R/'.colab_owner_prod'
 with owner.open('x') as f:f.write(f'T3 run2 production own {NAME} {time.time()}\n')
 start=time.time();event('allocation_begin')
 try:cli('new','-s',NAME,'--gpu','A100',timeout=125)
 except Exception as e:
  view=cmd(['colab','--auth','oauth2','sessions'],timeout=60)
  if NAME in view:raise RuntimeError('ambiguous A100 allocation, no fallback') from e
  if not re.search('503|412|Service Unavailable|Allocation refused',str(e),re.I):raise
  event('A100_refused_fallback_G4',error=str(e)[-350:]);start=time.time();cli('new','-s',NAME,'--gpu','G4',timeout=125)
 created=True;deadline=start+(58.0/rate)*3600
 gpu=cli('exec','-s',NAME,'-f',str(R/'gpu_probe.py'),timeout=100);event('gpu_ready',probe=gpu[-800:]);assert 'GPU' in gpu
 m=re.search(r'GPU\s+([^\n]+)',gpu);assert m,m
 # Fine mesh 131.6m cells; do not confuse name of accelerator with free VRAM.
 nums=re.findall(r'\b\d+\b',m.group(1));assert len(nums)>=2 and int(nums[-1])>29000,'GPU free VRAM <29 GB'
 host=re.search(r'MemAvailable:\s+(\d+)',gpu);assert host and int(host.group(1))>24*1024*1024,'host RAM <24 GiB'
 safe_deadline(400)
 for local,remote in [(R/'stage_fixed_bundle.tar.gz','/content/t3_run2_bundle.tar.gz'),(R/'remote_worker_run2.py','/content/t3_run2_worker.py')]:
  cli('upload','-s',NAME,str(local),remote,timeout=160)
 safe_deadline(400)
 launch=cli('exec','-s',NAME,'-f',str(R/'launch_run2.py'),'--env',f'T3_DEADLINE={deadline}','--env',f'T3_RATE={rate}',timeout=150)
 event('launch_receipt',receipt=launch[-700:]);assert 'RUN2_LAUNCHED_PID' in launch or 'RUN2_LAUNCH_PREPARED' in probe(),'launch uncertain; inspect remote before retry'
 keep=[str(Path.home()/'bin/colab-keepalive'),'--config',str(CFG),'-s',NAME,'--log','/content/t3_run2_out/run.log','--until-marker','/content/t3_run2_out/run.done','--pull','/content/t3_run2_out/run.log:'+str(R/'run2_progress.log'),'--pull','/content/t3_run2_out/*_solver.log:'+str(R/'solver_log_pull'),'--final-pull','/content/t3_run2_out/*.zip:'+str(R/'final_pull'),'--final-pull','/content/t3_run2_out/*_solver.log:'+str(R/'final_pull_logs'),'--final-pull','/content/t3_run2_out/run.log:'+str(R/'final_pull_logs'),'--final-max-mb','1000','--expect-hours','8','--max-hours','9','--no-remind','--detach']
 event('keepalive_start',receipt=cmd(keep,timeout=115)[-700:])
 last_seen=set();misses=0
 while time.time()<deadline-170:
  time.sleep(45)
  try:
   status=probe();misses=0
  except BaseException as e:
   misses+=1;event('probe_error',count=misses,error=str(e)[-400:]);
   if misses>=3:break
   continue
  for case in re.findall(r'ZIP\s+(dx\S+_s\d+\.zip)',status):
   if case not in last_seen:
    download_results();last_seen.add(case)
  if 'done True' in status or 'failed True' in status:break
 event('remote_terminal_or_deadline',status=probe()[-800:] if time.time()<deadline-130 else 'deadline')
 results=download_results()
 if len(results)==4:event('all_verified',cases={k:hashfile(R/(k+'_run2.zip')) for k in results})
 else:event('partial_results',cases=list(results));
 # Leave scientific judgment and plotting to the Research Chat wake-up.
 return len(results)==4
def stop():
 if not created:return
 try:
  cli('download','-s',NAME,'/content/t3_run2_out/run.log',str(R/'remote_run2.log'),timeout=90)
 except BaseException as e:event('remote_log_download_unavailable',error=str(e)[-350:])
 for case in ('dx1p0_s101','dx0p5_s101','dx1p0_s102','dx0p5_s102'):
  p=R/(case+'_solver_run2.log')
  if not p.exists():
   try:cli('download','-s',NAME,f'/content/t3_run2_out/{case}_solver.log',str(p),timeout=120);event('solver_log_downloaded',case=case,sha256=hashfile(p))
   except BaseException as e:event('solver_log_absent',case=case,error=str(e)[-250:])
 try:cli('stop','-s',NAME,timeout=120);event('stop_called',CU_estimate=(time.time()-start)*rate/3600)
 except BaseException as e:event('stop_error',error=str(e)[-500:])
 try:
  view=cmd(['colab','--auth','oauth2','sessions'],timeout=60)
  event('stop_confirmed' if NAME not in view else 'stop_unconfirmed',CU_estimate=(time.time()-start)*rate/3600)
 except BaseException as e:event('stop_verify_error',error=str(e)[-400:])
 try:cmd(['systemctl','--user','stop','colab-keepalive-'+NAME],timeout=25,check=False)
 except BaseException:pass
if __name__=='__main__':
 try:ok=main();event('controller_finished',success=ok)
 except BaseException:
  event('controller_failed',trace=traceback.format_exc()[-2500:]);ok=False
 finally:stop()
 sys.exit(0 if ok else 2)
