import hashlib,json,pathlib,re,subprocess,sys,time,traceback,shutil
R=pathlib.Path(__file__).resolve().parent
BASE=['colab','--auth','oauth2']; rate=5.4
PAYLOAD=['t9b12_source.tar.gz','t9b12_manifest.json','t9b2_stage.tar.gz','t9b2_archive.json','t5_reference_worker.py','remote_worker_run2.py','worker_gate.py']
REQUIRED=set('channel_y_off_trace.csv channel_y_on_trace.csv cube_off_trace.csv cube_on_trace.csv stage_A_verdict.json stage_B_verdict.json off_city_actual_opencl.cl on_city_actual_opencl.cl off_city_flags.npz on_city_flags.npz gate1.json points80.json gate3_flags.json full_height_coverage.json city_2000_off_points80.json city_2000_on_points80.json city_2000_difference.json city_2000_off_mlups.json city_2000_on_mlups.json'.split())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def log(d,event,**kw):
 line=json.dumps(dict(at=time.time(),local=time.strftime('%m-%d %H:%M:%S %Z'),event=event,**kw),ensure_ascii=False)
 with (d/'events.jsonl').open('a') as f:f.write(line+'\n')
 print(line,flush=True)
def call(args,limit=30):
 try:
  c=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=limit);return c.returncode,c.stdout
 except subprocess.TimeoutExpired:return 124,'client timeout'
def endpoints(s):return set(re.findall(r'gpu-a100-[a-z0-9-]+',s,re.I))
def checked(x):
 rc,out=x
 if rc:raise RuntimeError(out[-700:])
 return out
def pull(cli,o,name,info):
 assert re.fullmatch(r'[\w.\-]+',name) and name not in ('.','..')
 data=o/name;side=o/(name+'.sha256')
 if not (data.is_file() and side.is_file()):
  for p in (data,side):
   if p.exists():continue
   tmp=p.with_name(p.name+'.partial');checked(cli(['download','/content/t9b14/out/'+p.name,str(tmp)],24));tmp.rename(p)
 assert data.stat().st_size==info['size']>0 and sha(data)==side.read_text().strip()==info['sha'],name
 return info['sha']
def work(d,name,ep,created,cfg):
 deadline=created+5.5*3600/rate; cutoff=deadline-130
 def cli(args,t=30):return call(BASE+['--config',str(cfg),args[0],'-s',name]+args[1:],t)
 def bounded(args,t=30):return cli(args,max(1,min(t,cutoff-time.time())))
 def upload(p,n):checked(bounded(['upload',str(p),'/content/'+n]))
 o=d/'evidence';o.mkdir();verified={};terminal=None;absent=0;may_run=False;ka=False;ka_ok=False;ack=False
 b=d/'t9b14_budget.json';b.write_text(json.dumps(dict(created=created,deadline=deadline,assumed_CU_per_h=rate)))
 log(d,'allocated',session=name,endpoint=ep,created=created,deadline=deadline,assumed_rate=rate)
 try:
  machine=checked(bounded(['exec','-f',str(R/'machine.py')]));log(d,'machine',output=machine[-1000:]);match=re.search(r'^.*A100.*,\s*(\d+),\s*(\d+)\s*$',machine,re.M);assert match and int(match[2])>=16000,machine
  for n in PAYLOAD:upload(R/n,n)
  upload(b,b.name); u=d/'t9b14_upload.json';u.write_text(json.dumps({n:sha(R/n) for n in PAYLOAD}|{b.name:sha(b)}));upload(u,u.name)
  assert cutoff-time.time()>=3150,'startup consumed the remaining full-chain budget'
  may_run=True
  rc,out=bounded(['exec','-f',str(R/'launch_gate.py')],45);log(d,'launch_reply',rc=rc,reply=out[-700:])
 except Exception as e:log(d,'startup_error',error=repr(e))
 while may_run and time.time()<cutoff:
  if not ka and cutoff-time.time()>65:
   rc,msg=call([str(pathlib.Path.home()/'bin/colab-keepalive'),'--config',str(cfg),'-s',name,'--log','/content/t9b14.log','--until-marker','/content/t9b14/out/run.done','--max-hours','2','--expect-hours','1','--no-remind','--pull','/content/t9b14.log:'+str(d/'worker_progress.log'),'--final-pull','/content/t9b14.log:'+str(d/'keepalive_final'),'--detach'],45)
   ka=rc==0;log(d,'keepalive_start',rc=rc,output=msg[-600:])
  kstat=pathlib.Path.home()/'platform/colab-keepalive'/f'{name}.json'
  if not ka_ok and kstat.exists():
   try:
    k=json.loads(kstat.read_text());ka_ok=k.get('exec_ok',0)>0
    if ka_ok:log(d,'keepalive_verified',exec_ok=k['exec_ok'])
   except (ValueError,OSError):pass
  try:
   reply=checked(bounded(['exec','-f',str(R/'probe_gate.py')],30));s=json.loads(next(x[6:] for x in reply.splitlines() if x.startswith('PROBE ')));absent=0
   log(d,'probe',alive=s['alive'],tail=s['log'][-260:],done=s['done'],failed=s['failed'])
   for n,info in s['ready'].items():
    if cutoff-time.time()<45:break
    if n not in verified:verified[n]=pull(bounded,o,n,info);log(d,'verified',file=n,sha=verified[n])
   if s['b_passed'] and not ack and REQUIRED<=verified.keys() and s['ready'].keys()==verified.keys() and not s['failed']:
    a=d/'host_ack.json';a.write_text(json.dumps(verified)); upload(a,'t9b14_ack_upload.json')
    p=d/'publish_ack.py';p.write_text("from pathlib import Path\nPath('/content/t9b14_ack_upload.json').replace('/content/t9b14/out/host_ack.json')\n")
    rc,msg=bounded(['exec','-f',str(p)]); ack=rc==0 or s['ack'];log(d,'ack',rc=rc)
   if (s['failed'] or s['done']) and s['ready'].keys()<=verified.keys():
    terminal='done' if s['done'] and REQUIRED<=verified.keys() and 'run.done' in verified else 'failed';break
  except Exception as e:
   log(d,'probe_or_handoff_error',error=repr(e));rc,v=call(BASE+['sessions'],18);absent=absent+1 if rc==0 and ep not in v else 0
   if absent>=3:break
  time.sleep(min(20,max(0,cutoff-time.time())))
 reason=terminal or ('endpoint_absent' if absent>=3 else 'deadline' if may_run else 'prelaunch_failed')
 if absent<3:
  for _ in range(3):
   rc,msg=cli(['stop'],min(35,max(1,deadline-time.time())));log(d,'stop_request',rc=rc,reply=msg[-350:]);vr,v=call(BASE+['sessions'],20)
   if vr==0 and ep not in v:break
  else:vr,v=call(BASE+['sessions'],20)
 else:vr,v=call(BASE+['sessions'],20)
 released=vr==0 and ep not in v; confirmed=time.time();log(d,'stop_check',endpoint=ep,released=released,reason=reason,confirmed_at=confirmed,CU_estimate=(confirmed-created)*rate/3600 if released else None,verified_count=len(verified))
 orc,orph=call([str(pathlib.Path.home()/'bin/colab-orphans')],35);log(d,'orphans',rc=orc,result=orph[-1400:])
 if ka:
  rc,msg=call(['systemctl','--user','stop','colab-keepalive-'+name],20);log(d,'keepalive_stop',rc=rc)
 return 0 if terminal=='done' and released else 2

def main():
 assert (R/'PREFLIGHT.ok').is_file()
 assert all(sha(R/n)==h for n,h in json.loads((R/'PREFLIGHT.ok').read_text()).items())
 with (R/'.campaign_owner').open('x') as f:f.write(str(time.time()))
 start=time.time()
 for i in range(12):
  t=start+1200*i
  if t>=start+14400:break
  time.sleep(max(0,t-time.time()))
  d=R/f'attempt_{i+1:02d}';d.mkdir();name=f'luw-t9b14-a100-1117-b{i+1:02d}';cfg=d/'sessions.json';(d/'.colab_owner').write_text(name+'\n')
  view=checked(call(BASE+['sessions']));assert name not in view
  before=endpoints(view); lo=time.time();log(d,'allocation_attempt',session=name,gpu='A100')
  rc,out=call(BASE+['--config',str(cfg),'new','-s',name,'--gpu','A100'],100);log(d,'allocation_reply',rc=rc,output=out[-1500:]); hi=time.time()
  local_rc,local=call(BASE+['--config',str(cfg),'sessions'],25)
  global_rc,v=call(BASE+['sessions'],25)
  named=[line for line in local.splitlines() if name in line]
  owned=endpoints('\n'.join(named)) or endpoints(out)
  if rc==0 and not owned:
   q,s=call(BASE+['--config',str(cfg),'status','-s',name],20)
   if q==0:owned=endpoints(s)
  if len(owned)==1 and not owned&before and global_rc==0 and owned<=endpoints(v):return work(d,name,next(iter(owned)),lo,cfg)
  if rc!=0 and re.search(r'503|412|allocation refused|service unavailable|precondition failed',out,re.I) and global_rc==0 and local_rc==0 and not named and not (endpoints(v)-before):
   log(d,'definite_refusal',fallback='G4 not permitted by governing project runtime rules');continue
  log(d,'allocation_unconfirmed_no_retry',owned=list(owned),global_rc=global_rc,local_rc=local_rc);return 2
 time.sleep(max(0,start+14400-time.time()));log(R,'allocation_window_expired',gpu='A100');return 2
if __name__=='__main__':sys.exit(main())
