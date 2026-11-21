"""Resumable-at-member-boundary Colab scheduler for ten distinct IC-month ACE2 rollouts.
Never re-run a member or overwrite an existing result. Stops each owned VM in finally.
"""
import subprocess,time,json,sys,os,datetime
from pathlib import Path
R=Path(__file__).resolve().parent
SESSION=['lab-ace-formal-1014','lab-ace-formal-b2-1014','lab-ace-formal-b3-1014','lab-ace-formal-b4-1014']
BATCH=[range(1,4),range(4,7),range(7,10),range(10,11)]
LOG=(R/'controller.jsonl').open('x',buffering=1)
def record(event,**data):
 d={'when':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-4))).isoformat(),'event':event,**data}
 LOG.write(json.dumps(d)+'\n');print(d,flush=True)
def cmd(*parts,timeout=120):
 r=subprocess.run(['colab','--auth','oauth2',*parts],capture_output=True,text=True,timeout=timeout)
 if r.returncode:raise RuntimeError(f'colab {parts}: {r.returncode} {r.stdout[-1000:]} {r.stderr[-1000:]}')
 if 'Traceback (most recent call last)' in r.stdout or '---------------------------------------------------------------------------' in r.stdout:raise RuntimeError(f'remote traceback: {r.stdout[-3000:]}')
 return r.stdout
# Using stdin scripts permits short checks without mutating the remote workspace.
def query(session,code,timeout=80):
 r=subprocess.run(['colab','--auth','oauth2','exec','-s',session,'--timeout',str(timeout)],input=code,capture_output=True,text=True,timeout=timeout+40)
 if r.returncode:raise RuntimeError(f'exec {session}: {r.stdout[-800:]} {r.stderr[-800:]}')
 if 'Traceback (most recent call last)' in r.stdout:raise RuntimeError(f'query traceback {r.stdout[-2000:]}')
 return r.stdout

def prepare(session,batchnum):
 names=cmd('sessions')
 if session in names:raise RuntimeError('Session name collision '+session)
 owner=R/f'.colab_owner_batch{batchnum}'
 with owner.open('x') as f:f.write(f'formal-round controller batch {batchnum} {session}\n')
 record('NEW',session=session)
 cmd('new','-s',session,'--gpu','A100',timeout=180)
 cmd('install','-s',session,'fme==2026.8.1','huggingface_hub','netcdf4',timeout=300)
 cmd('restart-kernel','-s',session,timeout=120)
 query(session,"from pathlib import Path;Path('/content/ace_formal/reference').mkdir(parents=True,exist_ok=True);print('READY')\n")
 for name,remote in [('run_member.py','/content/ace_formal/run_member.py'),('stage_inputs.py','/content/ace_formal/stage_inputs.py'),('grid_and_weights.json','/content/ace_formal/reference/grid_and_weights.json')]:
  p=R/name if name!='grid_and_weights.json' else R/'reference'/name
  cmd('upload','-s',session,str(p),remote,timeout=120)
 r=cmd('exec','-s',session,'--timeout','600','-f',str(R/'stage_inputs.py'),timeout=650)
 if 'STAGING_DONE 47' not in r:raise RuntimeError('stage incomplete '+r[-2000:])
 record('STAGED',session=session)

def remote_state(session,month):
 code=f"from pathlib import Path\nimport json,os,shutil\np=Path('/content/ace_formal/members/m{month:02d}'); f=p/'exit.json'; d={{'exit':json.loads(f.read_text()) if f.exists() else None,'points':(p/'cold_points.npz').exists(),'tail':(p/'model.log').read_text()[-200:] if (p/'model.log').exists() else '', 'disk_free':shutil.disk_usage('/content').free}};print('STATE_JSON',json.dumps(d))\n"
 out=query(session,code)
 return json.loads(out.split('STATE_JSON',1)[1].strip().splitlines()[0])

def retrieve(session,month):
 root=R/'members'/f'm{month:02d}'
 root.mkdir(parents=True,exist_ok=False)
 for remote,local in [(f'/content/ace_formal/members/m{month:02d}/cold_points.npz','cold_points.npz'),(f'/content/ace_formal/members/m{month:02d}/exit.json','exit.json'),(f'/content/ace_formal/members/m{month:02d}/config.yaml','config.yaml'),(f'/content/ace_formal/members/m{month:02d}/model.log','model.log'),(f'/content/ace_formal/members/m{month:02d}.launcher.log','launcher.log')]:
  cmd('download','-s',session,remote,str(root/local),timeout=180)
 assert json.loads((root/'exit.json').read_text())['returncode']==0
 assert (root/'cold_points.npz').stat().st_size>100000
 record('PRESERVED',session=session,month=month,bytes=(root/'cold_points.npz').stat().st_size)

def do_batch(session,months,first=False):
 if not first:prepare(session,months.start)
 try:
  for month in months:
   if (R/'members'/f'm{month:02d}').exists():raise RuntimeError('Member result already exists '+str(month))
   if not (first and month==1):
    r=cmd('exec','-s',session,'--timeout','30','--env',f'MONTH={month}','-f',str(R/'launch_member.py'),timeout=80)
    if f'MEMBER_STARTED m{month:02d}' not in r:raise RuntimeError('Launch not confirmed '+r[-1200:])
    record('STARTED',session=session,month=month)
   deadline=time.monotonic()+5*3600
   while True:
    d=remote_state(session,month)
    record('PROGRESS',session=session,month=month,points=d['points'],exit=d['exit'],disk_free=d['disk_free'],tail=d['tail'])
    if d['exit'] and d['exit']['returncode']!=0:raise RuntimeError(f'model failed {month}: {d}')
    if d['points']:
     assert d['exit'] and d['exit']['returncode']==0
     retrieve(session,month);break
    if time.monotonic()>deadline:raise RuntimeError('Time limit for member '+str(month))
    time.sleep(240)
  if first:
   cmd('download','-s',session,'/content/ace_formal/staging_manifest.json',str(R/'staging_manifest.json'))
  record('BATCH_DONE',session=session,months=list(months))
 finally:
  # Stop even after a remote failure: owned GPU may otherwise continue billing.
  record('STOPPING',session=session)
  try:
   cmd('stop','-s',session,timeout=120)
   if session in cmd('sessions'):raise RuntimeError('Session still listed after stop')
   record('STOPPED',session=session)
   owner=R/('.colab_owner' if first else f'.colab_owner_batch{months.start}')
   if owner.exists():owner.unlink()
  except Exception as e:record('STOP_ERROR',session=session,error=repr(e));raise

try:
 for k,(s,ms) in enumerate(zip(SESSION,BATCH)):
  do_batch(s,ms,first=(k==0))
 record('ALL_MEMBERS_DONE',count=10)
except Exception as e:
 record('ERROR',message=repr(e));raise
finally:LOG.close()
