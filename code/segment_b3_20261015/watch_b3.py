"""Independent owned-session budget stop; never submit/restart a run."""
import datetime as dt, hashlib, json, pathlib, subprocess, time
D=pathlib.Path(__file__).parent
S='ideas-convective-r2-B3-1015'
CFG=D/'colab_state.json'
ALLOC=dt.datetime.fromisoformat('2026-10-15T12:59:00-04:00') # conservative before actual new
CAP=78.0 # margin below 81 CU including setup, polling and teardown
RATE=6.85

def call(args,timeout=100):
 try:
  p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
  return p.returncode,p.stdout+p.stderr
 except Exception as e:return 99,repr(e)
def cli(*args):return ['colab','--auth','oauth2','--config',str(CFG),*args]
def event(kind,**kw):
 with (D/'budget_b3.jsonl').open('a') as f:f.write(json.dumps(dict(at=dt.datetime.now().astimezone().isoformat(),kind=kind,**kw))+'\n')

while True:
 elapsed=(dt.datetime.now(dt.timezone.utc)-ALLOC).total_seconds()/3600
 rc,u=call(['colab','--auth','oauth2','usage'],45)
 rc2,files=call(cli('ls','-s',S,'/content'),75)
 marker=(rc2==0 and 'r2_segment_b.done' in files)
 event('check',hours=round(elapsed,4),estimated_cu=round(elapsed*RATE,3),usage=u[-250:],remote_ls_rc=rc2,marker=marker)
 if marker or elapsed*RATE>=CAP:
  event('trigger',reason='marker' if marker else 'budget',hours=elapsed,estimated_cu=elapsed*RATE)
  break
 if rc2!=0:
  rs,sessions=call(cli('sessions'),60)
  if rs==0 and S not in sessions:
   event('session_gone',sessions=sessions[-600:]);raise SystemExit(2)
 time.sleep(120)

# Unique archival filenames; preserve all previous pulls and validate exact contents.
for name,remote in [('checkpoint','r2_conus_main.jsonl'),('groups','r2_segment_b_groups.jsonl'),('log','segment_b3.log'),('marker','r2_segment_b.done')]:
 dst=D/(name+'_terminal_'+dt.datetime.now().strftime('%m%d_%H%M%S')+('.jsonl' if name in ('checkpoint','groups') else '.txt'))
 rc,out=call(cli('download','-s',S,'/content/'+remote,str(dst)),180)
 if rc==0 and dst.exists():
  b=dst.read_bytes();event('archive',name=name,path=str(dst),size=len(b),sha256=hashlib.sha256(b).hexdigest(),rows=len(b.splitlines()))
 else:event('archive_error',name=name,rc=rc,message=out[-700:])
rc,out=call(cli('stop','-s',S),180);event('stop',rc=rc,message=out[-700:])
rc,out=call(cli('sessions'),60);event('verify_absent',rc=rc,absent=S not in out,sessions=out[-900:])
rc,out=call(['colab','--auth','oauth2','usage'],60);event('final_usage',rc=rc,usage=out[-500:])
