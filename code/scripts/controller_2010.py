"""Sequential ACE2 Colab ensemble. Never infer simulation failure from a CLI timeout."""
import subprocess,time,json,sys,datetime,os
from pathlib import Path
R=Path(__file__).resolve().parent; P=R.parent
CONFIG=str(R/'sessions.json'); LOG=R/'controller.jsonl'
RATE=5.46; FIRST_CU=13.58; LOST_CU=3.02+1.513

def rec(event,**kw):
 d={'time':datetime.datetime.now().astimezone().isoformat(),'event':event,**kw}
 with LOG.open('a') as f:f.write(json.dumps(d,default=str)+'\n')
 print(d,flush=True)
def cli(*args,timeout=180,inp=None,private=True):
 cmd=['colab','--auth','oauth2']+(['--config',CONFIG] if private else [])+list(args)
 p=subprocess.run(cmd,input=inp,text=True,capture_output=True,timeout=timeout)
 if p.returncode or 'Traceback (most recent call last)' in p.stdout:raise RuntimeError(f'{cmd}: {p.returncode} {p.stdout[-1000:]} {p.stderr[-1000:]}')
 return p.stdout
def query(s,code):
 return cli('exec','-s',s,'--timeout','70',timeout=160,inp=code)
def observe(s,m,phase,marker,log,deadline_hours):
 start=time.monotonic();failures=0;first_failure=None
 code=f'''import json,os,time\nfrom pathlib import Path\np=Path({log!r}); m=Path({marker!r}); print('ACE_STATE '+json.dumps({{'done':m.exists(),'log_tail':p.read_text()[-500:] if p.exists() else '', 'log_age':round(time.time()-p.stat().st_mtime) if p.exists() else None}}))\n'''
 while True:
  try:
   out=query(s,code)
   state=json.loads(out.split('ACE_STATE ',1)[1].splitlines()[0])
   failures=0;first_failure=None
   rec('PROGRESS',member=m,phase=phase,**state)
   if state['done']:return state
   if phase=='staging' and ('Traceback (most recent call last)' in state['log_tail'] or 'Error:' in state['log_tail']):raise RuntimeError('staging traceback: '+state['log_tail'])
   if phase=='inference' and 'MEMBER_DONE' in state['log_tail'] and not state['done']:raise RuntimeError('summary marker missing despite MEMBER_DONE')
   if state['log_age'] and state['log_age']>2700:raise RuntimeError('remote log stale >45m; inspect remote before stop')
  except (subprocess.TimeoutExpired,RuntimeError,ValueError,IndexError) as exc:
   if 'staging traceback:' in str(exc) or 'remote log stale' in str(exc) or 'summary marker missing' in str(exc):raise
   failures+=1;first_failure=first_failure or time.monotonic()
   rec('POLL_RETRY',member=m,phase=phase,streak=failures,error=repr(exc)[:500])
   if failures>=5 and time.monotonic()-first_failure>=900:
    raise RuntimeError('five failed probes over >=15m; connectivity uncertain, leave session running for manual inspection') from exc
  if time.monotonic()-start>deadline_hours*3600:raise RuntimeError('phase deadline; inspect remote before stop')
  time.sleep(240)
def keepalive(s,phase,m):
 root='/content/ace_formal'; marker=(f'{root}/staging_2010.done' if phase=='staging' else f'{root}/members/m{m:02d}/summary.json')
 log=(f'{root}/staging_2010.log' if phase=='staging' else f'{root}/members/m{m:02d}/model.log')
 cmd=[str(Path.home()/'bin/colab-keepalive'),'--config',CONFIG,'-s',s,'--log',log,'--until-marker',marker,'--max-hours','10','--stale-min','0','--every','240','--detach']
 p=subprocess.run(cmd,text=True,capture_output=True,timeout=40)
 rec('KEEPALIVE',member=m,phase=phase,code=p.returncode,output=(p.stdout+p.stderr)[-400:])
 if p.returncode:raise RuntimeError('keepalive did not start')
def prep(s,m):
 if s in cli('sessions',private=False):raise RuntimeError('session collision '+s)
 owner=R/f'm{m:02d}.owner';owner.open('x').write(f'ideas #formal-ten 1979-{m:02d} {s} {datetime.datetime.now().astimezone().isoformat()}\n')
 rec('ALLOCATE',member=m,session=s)
 cli('new','-s',s,'--gpu','A100',timeout=240)
 cli('install','-s',s,'fme==2026.8.1','huggingface_hub','netcdf4',timeout=900)
 cli('restart-kernel','-s',s,timeout=180)
 query(s,"from pathlib import Path;Path('/content/ace_formal/reference').mkdir(parents=True,exist_ok=True);print('READY')\n")
 for local,remote in [(R/'run_member_2010.py','/content/ace_formal/run_member_2010.py'),(R/'launch_2010.py','/content/ace_formal/launch_2010.py'),(R/'reduce_points.py','/content/ace_formal/reduce_points.py'),(R/'threshold.json','/content/ace_formal/threshold.json'),(R/'stage_2010.py','/content/ace_formal/stage_2010.py'),(R/'launch_stage_2010.py','/content/ace_formal/launch_stage_2010.py'),(P/'reference/grid_and_weights.json','/content/ace_formal/reference/grid_and_weights.json')]:
  cli('upload','-s',s,str(local),remote,timeout=240)
 out=cli('exec','-s',s,'--timeout','60',timeout=160,inp="exec(open('/content/ace_formal/launch_stage_2010.py').read())\n")
 if 'STAGING_STARTED' not in out:raise RuntimeError('stage launch unconfirmed; inspect remote before re-launch: '+out[-300:])
 keepalive(s,'staging',m)
 st=observe(s,m,'staging','/content/ace_formal/staging_2010.done','/content/ace_formal/staging_2010.log',3)
 manifest=json.loads(query(s,"import json;print('ACE_MANIFEST '+json.dumps(json.load(open('/content/ace_formal/staging_manifest_2010.json'))))\n").split('ACE_MANIFEST ',1)[1].splitlines()[0])
 assert len(manifest['files'])==35
 rec('STAGED',member=m,session=s,files=35)
 # The staging watcher uses this session's unit name; release it before model watcher.
 unit='colab-keepalive-'+s
 subprocess.run(['systemctl','--user','stop',unit],capture_output=True,text=True,timeout=30)
 for _ in range(15):
  q=subprocess.run(['systemctl','--user','is-active',unit],capture_output=True,text=True,timeout=10)
  if q.stdout.strip()!='active':break
  time.sleep(2)
 else:raise RuntimeError('stage keepalive still active; inspect before starting model')
def retrieve(s,m):
 out=R/f'm{m:02d}';out.mkdir(exist_ok=False)
 remote=f'/content/ace_formal/members/m{m:02d}'
 for fn in ['summary.json','exit.json','config.yaml','model.log']:
  cli('download','-s',s,remote+'/'+fn,str(out/fn),timeout=300)
 cli('download','-s',s,remote+'.launcher.log',str(out/'launcher.log'),timeout=180)
 if m==2:cli('download','-s',s,'/content/ace_formal/staging_manifest_2010.json',str(R/'staging_manifest_2010.json'),timeout=180)
 d=json.loads((out/'exit.json').read_text());assert d['returncode']==0 and d['month']==m
 summary=json.loads((out/'summary.json').read_text())
 assert summary['member']==m and len(summary['maxima'])==30 and len(summary['pot_excess'])==30
 assert all(len(row)==8 for row in summary['maxima'])
 rec('PRESERVED',member=m,session=s,wall_s=d['wall_s'],bytes=(out/'summary.json').stat().st_size)
def member(m):
 s=f'lab-ace-ten-m{m:02d}-1015b';owner=R/f'm{m:02d}.owner';begin=time.monotonic()
 if (R/f'm{m:02d}').exists() or owner.exists():raise RuntimeError('Existing result/owner: '+str(m))
 completed=[json.loads((R/f'm{k:02d}'/'exit.json').read_text()) for k in range(2,m) if (R/f'm{k:02d}'/'exit.json').exists()]
 projection=FIRST_CU+LOST_CU+sum((v['wall_s']+900)/3600*RATE for v in completed)+(11-m)*((sum(v['wall_s'] for v in completed)/len(completed)) if completed else 5000)/3600*RATE
 rec('FORECAST',member=m,projected_total_cu=projection)
 if projection>100:raise RuntimeError('Projected >100 CU; pause before next allocation')
 allocated=False;safe_to_stop=False
 try:
  prep(s,m);allocated=True
  out=cli('exec','-s',s,'--env',f'MONTH={m}','--timeout','60','-f',str(R/'launch_2010.py'),timeout=160)
  if f'MEMBER_STARTED m{m:02d}' not in out:raise RuntimeError('launch uncertain; inspect remote before stopping '+out[-300:])
  rec('STARTED',member=m,session=s)
  keepalive(s,'inference',m)
  observe(s,m,'inference',f'/content/ace_formal/members/m{m:02d}/summary.json',f'/content/ace_formal/members/m{m:02d}/model.log',6)
  state=json.loads(query(s,f"import json;print('ACE_EXIT '+json.dumps(json.load(open('/content/ace_formal/members/m{m:02d}/exit.json'))))\n").split('ACE_EXIT ',1)[1].splitlines()[0])
  if state['returncode']!=0:raise RuntimeError('model failed '+repr(state))
  retrieve(s,m);safe_to_stop=True
 except Exception as e:
  rec('MEMBER_ERROR',member=m,session=s,error=repr(e))
  # A timeout is not evidence of a dead job. Keep session alive for inspection.
  raise
 finally:
  if safe_to_stop:
   cli('stop','-s',s,timeout=240)
   if s in cli('sessions',private=False):raise RuntimeError('stop not confirmed')
   rec('STOPPED',member=m,session=s,session_hours=(time.monotonic()-begin)/3600,estimated_cu=(time.monotonic()-begin)/3600*RATE)
   owner.unlink(missing_ok=True)
if __name__ == '__main__':
 start=int(sys.argv[1]) if len(sys.argv)>1 else 2
 assert 2 <= start <= 10
 for m in range(start,11):
  try:member(m)
  except Exception as e:rec('HALTED',member=m,error=repr(e));raise
 rec('ALL_NINE_PRESERVED',members=list(range(2,11)))
