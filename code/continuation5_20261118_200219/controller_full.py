#!/usr/bin/env python3
"""T15 A100-only ordered controller. Inert unless --authorized-run + sealed preflight."""
import hashlib,json,pathlib,re,subprocess,sys,time,uuid,argparse
R=pathlib.Path(__file__).resolve().parent
REF=None
BASE=['colab','--auth','oauth2'];RATE=5.4
CASES=('E3_native',)
PAYLOAD=('worker_full.py','remote_worker_run2.py','remote_io_full.py','t15_stage.tar.gz','t15_manifest.json','assert_e3.py','t15_budget.json')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def log(*a):print(*a,flush=True)
def raw(args,timeout=30):
 try:
  p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,stdin=subprocess.DEVNULL,timeout=timeout)
  return p.returncode,p.stdout
 except subprocess.TimeoutExpired:return 124,'CLI_TIMEOUT (ambiguous; reconcile before another state change)'
def checked(pair):
 rc,out=pair
 if rc:raise OSError(out[-1200:])
 return out
def retry(kind,fn,deadline):
 for i in range(5):
  try:
   x=fn();log('STEP_OK',kind,i+1);return x
  except (OSError,TimeoutError) as e:
   log('TRANSIENT',kind,i+1,repr(e))
   if i==4 or time.time()>=deadline:raise
   time.sleep(min(30*2**i,max(0,deadline-time.time())))
def main(authorized):
 if not authorized:raise SystemExit('inert: pass explicit --authorized-run')
 seal=json.loads((R/'PREFLIGHT_v2.ok').read_text())
 if set(seal)!={'worker_full.py','remote_worker_run2.py','remote_io_full.py','t15_stage.tar.gz','t15_manifest.json','assert_e3.py','controller_full.py','machine.py','EXPERIMENT_CARD.md'}:raise SystemExit('incomplete preflight seal')
 for n,h in seal.items():
  p=R/n
  if sha(p)!=h:raise SystemExit('preflight hash mismatch '+n)
 (R/'.colab_owner').open('x').write('T15 continuation #76dcd358 owned '+str(time.time())+'\n')
 global_before=checked(raw(BASE+['sessions']));window=time.time();ep=None
 events=(R/'allocation_events.log').open('x',buffering=1);sys.stdout=events
 while time.time()-window<4*3600:
  name='luw-t15-a100-'+uuid.uuid4().hex[:8];d=R/('session_'+name);d.mkdir();cfg=d/'sessions.json';o=d/'evidence';o.mkdir()
  if name in global_before:raise RuntimeError('session name collision')
  def cli(args,t=35):return raw(BASE+['--config',str(cfg),args[0],'-s',name]+args[1:],t)
  attempted=time.time();rc,msg=cli(['new','--gpu','A100'],100);log('ALLOC',name,rc,msg)
  after=checked(raw(BASE+['sessions']));local=checked(raw(BASE+['--config',str(cfg),'sessions']))
  candidates=set(re.findall(r'gpu-a100-[a-z0-9-]+','\n'.join(x for x in local.splitlines() if name in x)+'\n'+msg))
  owned={x for x in candidates if x in after and x not in global_before}
  if len(owned)==1:ep=owned.pop();created=attempted;break
  if rc==0 or not re.search(r'503|412|Service Unavailable|Allocation refused|precondition failed',msg,re.I) or name in after or candidates:
   raise RuntimeError('allocation ambiguous, no retry; reconcile exact endpoint')
  log('DEFINITE_503',name)
  if window+4*3600-time.time()<1200:break
  time.sleep(max(0,attempted+1200-time.time()))
 if not ep:log('NO_A100_WITHIN_WINDOW');return 2
 previous_cu=0.0
 remaining_cu=1.5
 cut=created+remaining_cu*3600/RATE-180;hard=created+remaining_cu*3600/RATE
 log('OWNED_ENDPOINT',ep,'created_assumed',created,'PREVIOUS_CU_ESTIMATE',previous_cu,'CU_CUTOFF',cut)
 result='unconfirmed';ka=False;acks=[];verified={}
 def bounded(args,t=35):
  if time.time()>=cut:raise TimeoutError('CU cutoff')
  return cli(args,max(.1,min(t,cut-time.time())))
 def upload(src,n):return retry('upload '+n,lambda:checked(bounded(['upload',str(src),'/content/'+n])),cut)
 def remote(code):
  f=d/('exec_'+uuid.uuid4().hex+'.py');f.write_text("import sys;sys.path.insert(0,'/content')\nimport remote_io_full as io\n"+code+'\n')
  return retry('exec',lambda:checked(bounded(['exec','-f',str(f)],40)),cut)
 def probe():
  text=retry('probe',lambda:remote("print('T15_PROBE '+io.json.dumps(io.probe(io.C)),flush=True)"),cut)
  prefix='T15_PROBE '
  rows=[x[len(prefix):] for x in text.splitlines() if x.startswith(prefix)]
  if len(rows)!=1:raise OSError('probe output absent')
  return json.loads(rows[0])
 def download(n,dst):return retry('download '+n,lambda:checked(bounded(['download','/content/t15/out/'+n,str(dst)],55)),cut)
 def ack(label,hashes):
  ackfile=d/(label+'.ack.pending');ackfile.write_text(json.dumps(hashes));upload(ackfile,ackfile.name)
  for i in range(5):
   try:
    out=remote(f"print('ACK_PRESENT', (io.C/'t15/out/{label}.ack.json').is_file(),flush=True)")
    if 'ACK_PRESENT True' in out:return
    remote(f'io.ack(io.C,{label!r})');return
   except (OSError,TimeoutError) as e:log('ACK_RETRY',label,i,repr(e))
  raise OSError('ACK unconfirmed')
 def collect():
  while time.time()<cut:
   try:
    listing=probe()
    for n,info in listing.items():
     if n in verified:continue
     if not re.fullmatch(r'[\w.-]+',n) or n.endswith('.vtk'):raise ValueError('unsafe output '+n)
     for item in (n,n+'.sha256'):download(item,o/(item+'.partial'))
     h=sha(o/(n+'.partial'))
     if not(h==info['sha']==(o/(n+'.sha256.partial')).read_text().strip() and (o/(n+'.partial')).stat().st_size==info['size']>0):raise OSError('transfer inconsistent '+n)
     for item in (n,n+'.sha256'):(o/(item+'.partial')).replace(o/item)
     verified[n]=h;log('VERIFIED',n,h)
    if len(acks)<len(CASES):
     label=CASES[len(acks)];hand=label+'_handoff.json'
     if hand in verified:
      hashes=json.loads((o/hand).read_text())['sha256']
      if set(hashes)<=set(verified) and all(verified[k]==v for k,v in hashes.items()):
       if json.loads((o/(label+'_exit.json')).read_text())['solver_exit']!=0:raise ValueError('solver exit '+label)

       if label=='E3_native':
        import csv
        with (o/(label+'_native_e3.csv')).open() as f:rows=list(csv.DictReader(f))
        if not rows:raise ValueError('E3 no records')
        gate=json.loads((o/(label+'_gate.json')).read_text())
        if not gate['pass']:raise ValueError('E3 failed')
       if label.startswith(('WM_','K3_')) and 'A100' not in (o/(label+'_solver.log')).read_text(errors='replace'):raise ValueError('solver device not A100')
       ack(label,hashes);acks.append(label);log('ACK',label)
    if 'run.failed' in verified:return 'failed'
    if 'run.done' in verified:
     done=json.loads((o/'run.done').read_text());return 'done' if done=={'verified_cases':list(CASES),'mode':'production'} and acks==list(CASES) else 'failed'
   except (OSError,TimeoutError) as e:log('RETRY_NO_STOP',repr(e))
   time.sleep(min(10,max(0,cut-time.time())))
  return 'deadline'
 try:
  machine=retry('machine',lambda:checked(bounded(['exec','-f',str(R/'machine.py')],30)),cut)
  rows=[x[12:] for x in machine.splitlines() if x.startswith('GPU_MACHINE ')]
  if len(rows)!=1:raise OSError('machine telemetry absent')
  info=json.loads(rows[0]);m=re.fullmatch(r'([^,]+),\s*(\d+),\s*(\d+)',info['stdout'].strip()) if info['rc']==0 else None
  if not m or 'A100' not in m[1] or int(m[3])<16000:raise ValueError('GPU not an A100 with >=16GiB free')
  log('MACHINE',m.groups())
  budget=d/'t15_budget.json';budget.write_text(json.dumps({'mode':'production','work_deadline':cut})+'\n')
  for n in PAYLOAD:upload(budget if n=='t15_budget.json' else R/n,n)
  receipt=d/'t15_upload.json';receipt.write_text(json.dumps({n:sha(budget if n=='t15_budget.json' else R/n) for n in PAYLOAD}))
  upload(receipt,receipt.name)
  if cut-time.time()<360:raise TimeoutError('insufficient remaining budget before compilation and E3')
  log('LAUNCH_REPLY',remote('io.launch(io.C)'))
  ka_args=[str(pathlib.Path.home()/'bin/colab-keepalive'),'--config',str(cfg),'-s',name,'--log','/content/t15.log','--until-marker','/content/t15/out/run.done','--max-hours','1','--expect-hours','1','--no-remind','--pull','/content/t15.log:'+str(d/'worker_progress.log'),'--final-pull','/content/t15/out/*.json:'+str(d/'final'),'--final-pull','/content/t15/out/*.csv:'+str(d/'final'),'--final-pull','/content/t15/out/*.sha256:'+str(d/'final'),'--detach']
  if 'RC_DELEGATE_CTX' in __import__('os').environ:ka_args[1:1]=['--ctx',__import__('os').environ['RC_DELEGATE_CTX']]
  rc,out=raw(ka_args,45)
  ka=rc==0;log('KEEPALIVE',rc,out)
  if not ka:raise OSError('keepalive failed; continue probing under CU cutoff')
  result=collect()
 except Exception as e:
  log('CONTROLLER_EXCEPTION_NO_EARLY_STOP',repr(e))
  if time.time()<cut:result=collect()
 finally:
  if result not in ('done','failed','deadline') and time.time()<cut:result=collect()
  if result not in ('done','failed') and time.time()<cut:raise RuntimeError('no valid stop condition; do not blind stop')
  log('STOP_REASON',result)
  released=False
  for _ in range(3):
   log('STOP',cli(['stop'],max(.1,min(35,hard-time.time()))))
   s,v=raw(BASE+['sessions'],max(.1,min(20,hard-time.time())));released=s==0 and ep not in v
   if released:break
  log('ENDPOINT',ep,'released',released,'CU_ESTIMATE',((time.time()-created)*RATE/3600 if released else None))
  if ka:log('KEEPALIVE_STOP',raw(['systemctl','--user','stop','colab-keepalive-'+name]))
  log('ORPHANS',raw([str(pathlib.Path.home()/'bin/colab-orphans')],35))
 return 0 if result=='done' and released else 2
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--authorized-run',action='store_true');sys.exit(main(p.parse_args().authorized_run))
