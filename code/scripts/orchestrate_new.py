"""Serial Colab orchestration for frozen C preregistration; no 工作站 numerical processing."""
import hashlib,json,os,subprocess,sys,time,datetime
from pathlib import Path
R=Path(__file__).resolve().parents[1]; S=R/'scripts'; CONFIG=R/'sessions.json'
TACC='[邮箱]'; SOCK=str(Path.home()/'.ssh/sockets/[邮箱]')
DEST='/work2/04448/[用户]/超算/AI_Weather/new_points_prereg/region_fields'
SSH=['ssh','-n','-o',f'ControlPath={SOCK}','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false',TACC]
SCP=['scp','-o',f'ControlPath={SOCK}','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false']
START=time.monotonic(); BUDGET=100; RATE=5.46

def rec(event,**kw):
 d={'time':datetime.datetime.now().astimezone().isoformat(),'event':event,**kw}
 with (R/'orchestrator.jsonl').open('a') as f:f.write(json.dumps(d,ensure_ascii=False)+'\n')
 print(json.dumps(d,ensure_ascii=False),flush=True)
def cmd(args,timeout=240,inp=None):
 for i in range(3):
  try:
   kw={'input':inp} if inp is not None else {'stdin':subprocess.DEVNULL}
   p=subprocess.run(args,**kw,text=True,capture_output=True,timeout=timeout)
   if p.returncode==0 and 'Traceback (most recent call last)' not in p.stdout:return p.stdout
   err=(p.stdout+p.stderr)[-1400:]
  except subprocess.TimeoutExpired as e:err=f'timeout {e}'
  rec('RETRY_IO',attempt=i+1,cmd=args[:5],error=err)
  if i<2:time.sleep(30*(i+1))
 raise RuntimeError(f'command failed {args[:6]}: {err}')
def cli(*args,timeout=240,inp=None):return cmd(['colab','--auth','oauth2','--config',str(CONFIG),*args],timeout,inp)
def query(s,code):return cli('exec','-s',s,'--timeout','70',timeout=170,inp=code)
def state(s,marker,log):
 code=f"from pathlib import Path;import json,time;p=Path({log!r});m=Path({marker!r});print('WXSTATE '+json.dumps({{'done':m.exists(),'tail':p.read_text()[-400:] if p.exists() else '', 'age_s':time.time()-p.stat().st_mtime if p.exists() else None}}))\n"
 return json.loads(query(s,code).split('WXSTATE ',1)[1].splitlines()[0])
def watch(s,marker,log,hours):
 t=time.monotonic()
 while True:
  try:
   a=state(s,marker,log);rec('WATCH',session=s,marker=marker,**a)
   if a['done']:return
   if 'Traceback (most recent call last)' in a['tail'] or 'CUDA out of memory' in a['tail']:raise RuntimeError('remote failure '+a['tail'])
  except Exception as e:
   rec('POLL_ERROR_NOT_STOPPING',session=s,error=repr(e))
   if isinstance(e,RuntimeError) and ('remote failure' in str(e)):raise
  if time.monotonic()-t>hours*3600:raise RuntimeError('deadline: leave session alive for inspection '+s)
  time.sleep(240)
def upload(s,local,remote):cli('upload','-s',s,str(local),remote,timeout=300)
def download(s,remote,local):
 if local.exists():raise RuntimeError('refuse overwrite '+str(local))
 cli('download','-s',s,remote,str(local),timeout=500)
 if not local.is_file() or not local.stat().st_size:raise RuntimeError('download not verified '+str(local))
def watcher(s,log,marker):
 out=cmd([str(Path.home()/'bin/colab-keepalive'),'--config',str(CONFIG),'-s',s,'--log',log,'--until-marker',marker,'--stale-min','0','--max-hours','10','--every','240','--detach'],90)
 rec('KEEPALIVE_STARTED',session=s,output=out[-300:])
def unwatch(s):
 subprocess.run(['systemctl','--user','stop','colab-keepalive-'+s],capture_output=True,timeout=60)
 for _ in range(20):
  p=subprocess.run(['systemctl','--user','is-active','colab-keepalive-'+s],capture_output=True,text=True)
  if p.stdout.strip()!='active':return
  time.sleep(2)
 raise RuntimeError('keepalive still active')
def stop(s):
 unwatch(s);cli('stop','-s',s,timeout=300);rec('STOPPED',session=s)
def remote_check():
 cmd(['ssh','-O','check','-o',f'ControlPath={SOCK}','x'],40)
 assert cmd(SSH+['test -d '+DEST+' && printf OK'],60).strip()=='OK'
def reference():
 s='wx-cnew-ref-1015';base='/content/ace_formal';r=base+'/reference'
 watch(s,r+'/batch.exit.json',r+'/batch.log',4)
 a=json.loads(query(s,f"import json;print('WXEXIT '+json.dumps(json.load(open('{r}/batch.exit.json'))))\n").split('WXEXIT ',1)[1].splitlines()[0]);assert a['returncode']==0,a
 a=json.loads(query(s,f"from pathlib import Path;import json;print('WXCOUNT '+json.dumps(len(list(Path('{r}').glob('cold_*.npz')))))\n").split('WXCOUNT ',1)[1].splitlines()[0]);assert a==30,a
 unwatch(s)
 for name in ('reduce_points.py','extract_pressure_new.py','launch_pressure.py'):upload(s,S/name,base+'/'+name)
 query(s,f"exec(open('{base}/reduce_points.py').read().replace('sys.argv[1]','\"reference\"',1))\n")
 # Do not execute reduce_points in the kernel after accidental argv substitution; verify its summary.
 x=query(s,f"from pathlib import Path;print('WXSUMMARY',Path('{base}/reference_summary.json').exists(),Path('{base}/threshold.json').exists())\n");assert 'WXSUMMARY True True' in x,x
 for name in ('reference_summary.json','threshold.json'):download(s,base+'/'+name,R/name)
 query(s,f"exec(open('{base}/launch_pressure.py').read())\n")
 watcher(s,r+'/pressure.log',r+'/pressure.exit.json')
 watch(s,r+'/pressure.exit.json',r+'/pressure.log',5)
 x=query(s,f"import json;print('WXEXIT '+json.dumps(json.load(open('{r}/pressure.exit.json'))))\n")
 assert json.loads(x.split('WXEXIT ',1)[1].splitlines()[0])['returncode']==0,x
 for name in ('pressure_minima.json','pressure_grid.json'):download(s,r+'/'+name,R/('era_'+name))
 stop(s);rec('REFERENCE_COMPLETE',elapsed_hours=(time.monotonic()-START)/3600)
def budget(k,prior):
 # Conservative forward projection: actual occupied time plus ten-member projected sessions.
 observed=max(sum(prior)/len(prior),1.4) if prior else 1.4
 projected=2+(sum(prior)+(11-k)*observed)*RATE+3
 rec('CU_FORECAST',member=k,projected_cu=projected,actual_session_hours=prior)
 if projected> BUDGET:raise RuntimeError(f'CU forecast {projected:.2f} > {BUDGET}; stop before next session')
def member(k,prior,reuse_allocated=False):
 budget(k,prior);remote_check()
 s=f'wx-cnew-m{k:02d}-1015';label=f'm{k:02d}';m='/content/ace_formal/members/'+label;base='/content/ace_formal'
 out=R/'results'/label
 if reuse_allocated:
  if k!=1 or not out.is_dir() or any(out.iterdir()):raise RuntimeError('unsafe resume: expected empty m01 result')
  check=cli('status','-s',s,timeout=90)
  if 'IDLE' not in check:raise RuntimeError('unsafe resume: existing VM not idle: '+check)
  rec('REUSE_IDLE_ALLOCATION',session=s)
 else:
  if out.exists():raise RuntimeError('existing member result; refuse duplicate '+label)
  out.mkdir(parents=True,exist_ok=False)
  cli('new','-s',s,'--gpu','A100',timeout=300);rec('ALLOCATED',session=s)
  cli('install','-s',s,'fme==2026.8.1','huggingface_hub','netcdf4',timeout=1200)
  cli('restart-kernel','-s',s,timeout=240)
 t=time.monotonic()
 query(s,"from pathlib import Path;Path('/content/ace_formal').mkdir(parents=True,exist_ok=True);print('WXDIR_READY')\n")
 for name in ('stage_2010.py','launch_stage_2010.py','run_member_new.py','reduce_points.py','sites_frozen.json','launch_2010.py'):
  upload(s,(R/name if name=='sites_frozen.json' else S/name),base+'/'+name)
 upload(s,R/'threshold.json',base+'/threshold.json')
 query(s,f"exec(open('{base}/launch_stage_2010.py').read())\n")
 watcher(s,base+'/staging_2010.log',base+'/staging_2010.done')
 watch(s,base+'/staging_2010.done',base+'/staging_2010.log',4)
 unwatch(s)
 x=query(s,f"import json;print('WXSTAGE '+json.dumps(json.load(open('{base}/staging_manifest_2010.json'))))\n")
 assert len(json.loads(x.split('WXSTAGE ',1)[1].splitlines()[0])['files'])==35
 # The launcher uses run_member_2010.py: provide the new implementation under that name.
 upload(s,S/'run_member_new.py',base+'/run_member_2010.py')
 x=cli('exec','-s',s,'--env',f'MONTH={k}','--timeout','70','-f',str(S/'launch_2010.py'),timeout=200)
 assert f'MEMBER_STARTED {label}' in x,x
 rec('MODEL_STARTED',session=s,member=k)
 watcher(s,m+'/model.log',m+'/complete.done')
 watch(s,m+'/complete.done',m+'.launcher.log',7)
 x=query(s,f"import json;print('WXEXIT '+json.dumps(json.load(open('{m}/exit.json'))))\n")
 assert json.loads(x.split('WXEXIT ',1)[1].splitlines()[0])['returncode']==0,x
 for fn in ('summary.json','exit.json','region_manifest.json','pressure_minima.json','config.yaml'):
  download(s,m+'/'+fn,out/fn)
 manifest=json.loads((out/'region_manifest.json').read_text());assert len(manifest['files'])>=31 and sum(q['steps'] for q in manifest['files'])==json.loads((out/'exit.json').read_text())['steps']
 dest=DEST+'/'+label;cmd(SSH+['mkdir -p '+dest+' && test -z "$(ls -A '+dest+')"'],60)
 entries=[];cache=R/'transfer';cache.mkdir(exist_ok=True)
 for q in manifest['files']:
  name=q['file'];local=cache/(label+'_'+name)
  if q['bytes']>190_000_000:raise RuntimeError('single region chunk exceeds 190 MB: '+name)
  download(s,m+'/region/'+name,local)
  assert local.stat().st_size==q['bytes'],(name,local.stat().st_size,q['bytes'])
  digest=hashlib.sha256(local.read_bytes()).hexdigest()
  cmd(SCP+[str(local),f'{TACC}:{dest}/{name}'],timeout=600)
  actual=cmd(SSH+[f'sha256sum {dest}/{name}'],timeout=120).split()[0]
  assert actual==digest,(name,digest,actual)
  entries.append({'file':name,'bytes':q['bytes'],'sha256':digest})
  # This is a transient transfer cache, not the preserved result. The verified TACC copy remains.
  local.unlink();rec('REGION_VERIFIED',member=k,file=name,bytes=q['bytes'],sha256=digest)
 (out/'tacc_manifest.json').write_text(json.dumps({'remote':dest,'entries':entries},indent=2))
 stop(s)
 spent=(time.monotonic()-t)/3600;prior.append(spent)
 rec('MEMBER_COMPLETE',member=k,session=s,session_hours=spent,estimated_cu=spent*RATE)
def main():
 lock=R/'orchestrator.lock'
 if lock.exists():
  old=int(lock.read_text())
  try:os.kill(old,0)
  except ProcessLookupError:pass
  else:raise RuntimeError('orchestrator still active: '+str(old))
 lock.write_text(str(os.getpid()))
 try:
  remote_check()
  if not all((R/n).is_file() for n in ('reference_summary.json','threshold.json','era_pressure_minima.json','era_pressure_grid.json')):reference()
  else:rec('REFERENCE_REUSED',reason='four local reference outputs already present')
  prior=[]
  for k in range(1,11):member(k,prior,reuse_allocated=(k==1))
  rec('ALL_COMPLETE',member_count=10,elapsed_hours=(time.monotonic()-START)/3600,estimated_cu=(time.monotonic()-START)/3600*RATE)
 except Exception as e:
  rec('HALTED_LEAVE_SESSION_RUNNING',error=repr(e));raise
if __name__=='__main__':main()
