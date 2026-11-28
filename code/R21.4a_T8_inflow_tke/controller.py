#!/usr/bin/env python3.10
"""T8 single owned Colab session; persist transfers and deadline; no blind finally stop."""
import pathlib,subprocess,json,time,hashlib,re,traceback,sys
R=pathlib.Path(__file__).resolve().parent;CFG=R/'sessions.json';NAME='luw-r214a-t8-inflow-tke-1117';O=R/'evidence';BASE=['colab','--auth','oauth2'];LOCAL=BASE+['--config',str(CFG)];EVENT=R/'events.jsonl'
ENDPOINT=None;created=None;deadline=None;rate=None;launched=False
BASELINE='6b57372b53206a9af04069bf25c0f756f77e78ef92d86d658a1495c863f4b279'
def log(ev,**kw):
 obj={'time':time.strftime('%m-%d %H:%M:%S %Z'),'event':ev,**kw}
 with EVENT.open('a') as f:f.write(json.dumps(obj,ensure_ascii=False)+'\n')
 print(json.dumps(obj,ensure_ascii=False),flush=True)
def cmd(a,timeout=120,check=True):
 p=subprocess.run(a,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout,stdin=subprocess.DEVNULL)
 log('command',cmd=a[:7],rc=p.returncode,tail=p.stdout[-350:])
 if check and p.returncode:raise RuntimeError('command failed '+str(a[:7])+' '+p.stdout[-400:])
 return p.stdout,p.returncode
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def eps(s):return set(re.findall(r'gpu-(?:a100|g4)-s-[a-z0-9-]+',s,re.I))
def remote(p,env=None,timeout=110):
 a=LOCAL+['exec','-s',NAME,'-f',str(R/p)]
 for k,v in (env or {}).items():a+=['--env',k+'='+str(v)]
 return cmd(a,timeout)[0]
def probe():
 s=remote('probe.py');q=[i for i in s.splitlines() if i.startswith('PROBE ')];assert q,s[-350:]
 return json.loads(q[-1][6:])
def pull(remote_path,name,required=True):
 p=O/name
 if not p.exists():
  try:cmd(LOCAL+['download','-s',NAME,remote_path,str(p)],210,required)
  except (subprocess.TimeoutExpired,RuntimeError,OSError) as e:
   if required:raise
   log('optional_pull_error',name=name,error=str(e)[-250:])
 if required:assert p.is_file() and p.stat().st_size>0
 return p
def stop(reason):
 log('stop_start',reason=reason,endpoint=ENDPOINT)
 for name in ('t8.log','run.done','run.failed','build.log','solver.log','exit.json','actual_opencl.cl','profile.json'):
  try:pull('/content/t8_out/'+name if name!='t8.log' else '/content/t8.log',name,False)
  except Exception as e:log('pull_error',name=name,error=str(e)[-150:])
 cmd(LOCAL+['stop','-s',NAME],140,False)
 s=cmd(BASE+['sessions'],100)[0];absent=ENDPOINT not in eps(s)
 log('stop_check',endpoint=ENDPOINT,absent=absent,estimated_CU=((time.time()-created)*rate/3600 if created and rate else None))
 cmd([str(pathlib.Path.home()/'bin/colab-orphans')],100,False)
 if not absent:log('PLATFORM_ALERT',message='owned endpoint still present; contact platform Lead')
 cmd(['systemctl','--user','stop','colab-keepalive-'+NAME],30,False)
def main():
 global ENDPOINT,created,deadline,rate,launched
 assert sha(R/'stage_t5.tar.gz')==json.loads((R/'archive.json').read_text())['sha256']
 assert not CFG.exists() and not O.exists() and not EVENT.exists() and not (R/'.colab_owner').exists()
 before=eps(cmd(BASE+['sessions'])[0]);assert NAME not in cmd(BASE+['sessions'])[0]
 (R/'.colab_owner').open('x').write('R21.4a-T8 researchos-uwind-luw 11-17\n');O.mkdir(exist_ok=False)
 allocation_start=time.time();roundno=0
 while time.time()-allocation_start<4*3600:
  roundno+=1
  for gpu in ('A100','G4'):
   try:text,rc=cmd(LOCAL+['new','-s',NAME,'--gpu',gpu],160,False)
   except subprocess.TimeoutExpired:raise RuntimeError('allocation ambiguous; reconcile session before action')
   if rc==0 and 'Session READY' in text:
    created=time.time();rate=5.4 if gpu=='A100' else 6.81;deadline=created+3*3600/rate-110
    diff=eps(cmd(BASE+['sessions'])[0])-before;assert len(diff)==1,diff;ENDPOINT=next(iter(diff))
    log('allocated',gpu=gpu,endpoint=ENDPOINT,created=created,deadline=deadline,rate_assumption=rate);break
   if not re.search('503|412|Service Unavailable|Allocation refused|precondition failed',text,re.I):raise RuntimeError('allocation ambiguous '+text[-400:])
   assert NAME not in cmd(BASE+['sessions'])[0];log('allocation_refused',round=roundno,gpu=gpu,response=text[-300:])
  if created:break
  wait=min(1200,max(0,allocation_start+4*3600-time.time()));log('backoff',seconds=wait)
  if wait:time.sleep(wait)
 if not created:log('allocation_window_exhausted');return 2
 try:
  for name in ('stage_t5.tar.gz','archive.json','B2u_reference_points.json','comparison.json','worker.py','remote_worker_run2.py','t5_sampler.py','launch.py','probe.py','ack.py'):
   cmd(LOCAL+['upload','-s',NAME,str(R/name),'/content/'+name],180)
  if time.time()+1250>deadline:raise RuntimeError('insufficient full-run budget after upload')
  try:receipt=remote('launch.py',{'T8_DEADLINE':str(deadline)},155)
  except (subprocess.TimeoutExpired,RuntimeError) as e:
   log('launch_uncertain',error=str(e)[-300:]);receipt=''
  if 'LAUNCHED' not in receipt:
   p=probe();assert p['tail'] or p['ready'] or p['done'] or p['failed'],'ambiguous launch, keep endpoint for reconcile'
  launched=True;log('launched',receipt=receipt[-160:])
  ka=[str(pathlib.Path.home()/'bin/colab-keepalive'),'--config',str(CFG),'-s',NAME,'--log','/content/t8.log','--proc','/content/worker.py','--until-marker','/content/t8_out/run.done','--stale-min','60','--max-hours','1','--expect-hours','0.6','--no-remind','--pull','/content/t8.log:'+str(O/'progress.log'),'--final-pull','/content/t8_out/profile.json:'+str(O),'--final-pull','/content/t8_out/exit.json:'+str(O),'--detach']
  log('keepalive_start',receipt=cmd(ka,120)[0][-450:])
  absent_count=0;ready=False;same=None
  while True:
   if time.time()>=deadline-70:
    log('deadline_reached');stop('deadline');return 2
   try:s=probe();absent_count=0
   except (subprocess.TimeoutExpired,RuntimeError,AssertionError,ValueError,OSError) as e:
    log('probe_error',error=str(e)[-350:]);cmd(LOCAL+['status','-s',NAME],70,False)
    absent=ENDPOINT not in eps(cmd(BASE+['sessions'],90)[0]);absent_count=absent_count+1 if absent else 0
    if absent_count>=3:log('endpoint_gone_3');return 2
    time.sleep(35);continue
   log('probe',ready=list(s['ready']),ack=s['ack'],done=s['done'],failed=s['failed'],tail=s['tail'][-160:])
   keys=('points80.json','upstream_slice.npz')
   if all(x+'.sha256' in s['ready'] for x in keys) and not ready:
    try:
     hashes=[]
     for name in keys:
      info=s['ready'][name+'.sha256'];p=pull('/content/t8_out/'+name,name)
      assert p.stat().st_size==info['size'] and sha(p)==info['sha']
      assert pull('/content/t8_out/'+name+'.sha256',name+'.sha256').read_text().strip()==info['sha'];hashes.append(info['sha'])
     same=hashes[0]==BASELINE
     p=json.loads((O/'points80.json').read_text());assert p['label']=='E_s101_off' and len(p['rows'])==80 and {int(q['id']) for q in p['rows']}==set(range(1,81))
     import numpy as np
     with np.load(O/'upstream_slice.npz') as n:
      assert n['tke'].shape==(62,201,61) and n['u_avg'].shape==(62,201,61,3) and np.isfinite(n['tke']).all()
     log('host_verified',same_points80=same,points_sha256=hashes[0],slice_sha256=hashes[1])
     for n in ('profile.json','solver.log','exit.json','actual_opencl.cl','build.log'):
      info=s['ready'].get(n+'.sha256')
      if info:assert sha(pull('/content/t8_out/'+n,n))==info['sha']
     pair=' '.join(hashes)
     try:receipt=remote('ack.py',{'T8_PAIR':pair})
     except (subprocess.TimeoutExpired,RuntimeError):receipt=''
     assert 'ACK' in receipt or probe()['ack'],'ACK unconfirmed'
     ready=True
    except (subprocess.TimeoutExpired,RuntimeError,AssertionError,OSError,ValueError) as e:log('verify_error',error=str(e)[-350:])
   if s['failed'] or (s['done'] and ready):
    stop('terminal');return 0 if s['done'] and ready and same else 2
   time.sleep(30)
 except BaseException as e:
  log('controller_error',error=str(e)[-500:],traceback=traceback.format_exc()[-1000:])
  if not launched and ENDPOINT:stop('prelaunch_error')
  elif ENDPOINT and time.time()>=deadline-70:stop('deadline_error')
  return 2
if __name__=='__main__':sys.exit(main())
