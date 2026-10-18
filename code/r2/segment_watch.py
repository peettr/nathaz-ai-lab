"""Owned Colab session budget watchdog; immutable pulls and verified stop."""
import argparse,datetime as dt,json,pathlib,re,subprocess,time
p=argparse.ArgumentParser();p.add_argument('--session',required=True);p.add_argument('--config',required=True);p.add_argument('--out',required=True);p.add_argument('--cap',type=float,required=True);p.add_argument('--rate',type=float,required=True);p.add_argument('--checkpoint',default='/content/r2_v1_main.jsonl');p.add_argument('--groups',default='/content/r2_segment_a_groups.jsonl');p.add_argument('--log',default='/content/segment_a.log');p.add_argument('--marker',default='/content/r2_segment_a.done');a=p.parse_args()
D=pathlib.Path(a.out);D.mkdir(parents=True,exist_ok=True);started=time.monotonic()
def call(args,timeout=120):
 try:
  q=subprocess.run(args,capture_output=True,text=True,timeout=timeout);return q.returncode,q.stdout+q.stderr
 except Exception as ex:return 99,repr(ex)
def cli(*args):return ['colab','--auth','oauth2','--config',a.config,*args]
def record(event,**kwargs):
 with (D/'watch.jsonl').open('a') as f:f.write(json.dumps({'at':dt.datetime.now().astimezone().isoformat(),'event':event,**kwargs})+'\n')
try:
 while True:
  elapsed=(time.monotonic()-started)/3600;rc,usage=call(['colab','--auth','oauth2','usage']);bal=re.search(r'Current balance:\s*([\d.]+)',usage)
  record('usage',elapsed_h=elapsed,estimate_cu=elapsed*a.rate,balance=float(bal.group(1)) if bal else None,raw=usage[-350:])
  rc,files=call(cli('ls','-s',a.session,'/content'),timeout=90)
  if rc or a.session not in call(cli('sessions'))[1]:record('session_gone',raw=files[-500:]);break
  if a.marker.split('/')[-1] in files:record('marker_seen');break
  if elapsed*a.rate>=a.cap-2:record('own_budget_guard',estimate_cu=elapsed*a.rate);break
  time.sleep(120)
finally:
 for remote,label in [(a.checkpoint,'checkpoint'),(a.groups,'groups'),(a.log,'log'),(a.marker,'marker')]:
  path=D/(label+'_'+dt.datetime.now().strftime('%m%d_%H%M%S')+pathlib.Path(remote).suffix)
  rc,text=call(cli('download','-s',a.session,remote,str(path)),timeout=180)
  record('pull',what=label,rc=rc,path=str(path) if rc==0 else None,message=text[-400:])
 rc,text=call(cli('stop','-s',a.session),timeout=180);record('stop',rc=rc,message=text[-400:])
 rc,text=call(cli('sessions'));record('sessions',rc=rc,own_present=a.session in text,raw=text[-1000:])
 rc,text=call(['colab','--auth','oauth2','usage']);record('usage_final',rc=rc,raw=text[-400:])
