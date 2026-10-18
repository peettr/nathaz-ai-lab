"""Monitor the already-running m01, preserve result, and stop before 20 CU.
Only this task's lab-ace-formal-1014 session is touched. No new runs.
"""
import datetime,json,subprocess,time
from pathlib import Path
R=Path(__file__).resolve().parent
S='lab-ace-formal-1014'
LOG=R/'budget_watch.jsonl'
# Conservative cap based on first allocated GPU at 19:05 EDT and 5.46 CU/hr.
DEADLINE=datetime.datetime(2026,10,14,22,30,tzinfo=datetime.timezone(datetime.timedelta(hours=-4)))
def rec(event,**kwargs):
 d={'time':datetime.datetime.now().astimezone().isoformat(),'event':event,**kwargs}
 with LOG.open('a') as f:f.write(json.dumps(d)+'\n')
 print(d,flush=True)
def run(*args,timeout=120,input=None):
 p=subprocess.run(['colab','--auth','oauth2',*args],input=input,text=True,capture_output=True,timeout=timeout)
 if p.returncode:raise RuntimeError((args,p.stdout[-1000:],p.stderr[-1000:]))
 return p.stdout
try:
 while True:
  now=datetime.datetime.now().astimezone()
  if now>=DEADLINE:
   rec('BUDGET_DEADLINE',estimated_cu=(now-datetime.datetime(2026,10,14,19,5,tzinfo=now.tzinfo)).total_seconds()/3600*5.46)
   break
  code="from pathlib import Path\nimport json\np=Path('/content/ace_formal/members/m01');e=p/'exit.json';print('WATCH_JSON',json.dumps({'exit':json.loads(e.read_text()) if e.exists() else None,'points':(p/'cold_points.npz').exists(),'tail':(p/'model.log').read_text()[-250:] if (p/'model.log').exists() else ''}))\n"
  o=run('exec','-s',S,'--timeout','70',timeout=110,input=code)
  d=json.loads(o.split('WATCH_JSON',1)[1].splitlines()[0].strip())
  rec('STATE',**d)
  if d['exit'] and d['exit']['returncode']!=0:break
  if d['points']:
   if not d['exit'] or d['exit']['returncode']!=0:raise RuntimeError('points without model exit')
   out=R/'members'/'m01';out.mkdir(parents=True,exist_ok=False)
   for filename in ['cold_points.npz','exit.json','config.yaml','model.log']:
    run('download','-s',S,f'/content/ace_formal/members/m01/{filename}',str(out/filename),timeout=180)
   run('download','-s',S,'/content/ace_formal/members/m01.launcher.log',str(out/'launcher.log'),timeout=180)
   run('download','-s',S,'/content/ace_formal/staging_manifest.json',str(R/'staging_manifest.json'),timeout=180)
   rec('PRESERVED',bytes=(out/'cold_points.npz').stat().st_size)
   break
  time.sleep(180)
except Exception as e:rec('ERROR',message=repr(e))
finally:
 try:
  rec('STOPPING');run('stop','-s',S,timeout=180)
  assignments=run('sessions')
  rec('STOPPED',absent=S not in assignments,other_assignments=assignments)
  if S in assignments:raise RuntimeError('session still listed')
  (R/'.colab_owner').unlink(missing_ok=True)
 except Exception as e:rec('STOP_ERROR',message=repr(e))
