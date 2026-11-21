#!/usr/bin/env python3
"""Owned A100 diagnostic; fail closed on ambiguous allocation and timeout."""
import hashlib,json,os,pathlib,re,subprocess,sys,time,uuid
R=pathlib.Path(__file__).resolve().parent;BASE=['colab','--auth','oauth2'];RATE=5.4;CASES=('d5','d6');PAYLOAD=('worker_diag.py','remote_diag.py','diag_stage.tar.gz','diag_manifest.json','diag_budget.json')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def raw(a,t=35):
 try:
  p=subprocess.run(a,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,stdin=subprocess.DEVNULL,timeout=t);return p.returncode,p.stdout
 except subprocess.TimeoutExpired:return 124,'CLI_TIMEOUT ambiguous'
def ok(pair):
 rc,out=pair
 if rc:raise OSError(out[-1500:])
 return out
def retry(kind,fn,deadline):
 for i in range(5):
  try:return fn()
  except (OSError,TimeoutError) as e:
   print('TRANSIENT',kind,i,repr(e),flush=True)
   if i==4 or time.time()>=deadline:raise
   time.sleep(min(30*2**i,max(0,deadline-time.time())))
def main():
 seal=json.loads((R/'PREFLIGHT.ok').read_text())
 if any(sha(R/n)!=h for n,h in seal.items()):raise RuntimeError('seal mismatch')
 (R/'.colab_owner').open('x').write('T17 A1b diagnosis; researchos-uwind-luw; luw-claude\n')
 before=ok(raw(BASE+['sessions']));window=time.time();ep=None
 events=(R/'allocation_events.log').open('x',buffering=1);sys.stdout=events
 while time.time()-window<4*3600:
  name='luw-t17-a1b-'+uuid.uuid4().hex[:8];d=R/('session_'+name);d.mkdir();cfg=d/'sessions.json';out=d/'evidence';out.mkdir()
  def cli(args,t=35):return raw(BASE+['--config',str(cfg),args[0],'-s',name]+args[1:],t)
  attempted=time.time();rc,msg=cli(['new','--gpu','A100'],100);print('ALLOC',name,rc,msg,flush=True)
  after=ok(raw(BASE+['sessions']));local=ok(raw(BASE+['--config',str(cfg),'sessions']))
  candidates=set(re.findall(r'gpu-a100-[a-z0-9-]+','\n'.join(x for x in local.splitlines() if name in x)+'\n'+msg))
  owned={x for x in candidates if x in after and x not in before}
  if len(owned)==1:ep=owned.pop();created=attempted;break
  if rc==0 or not re.search('503|412|Service Unavailable|Allocation refused|precondition failed',msg,re.I) or name in after or candidates:raise RuntimeError('ambiguous allocation')
  print('DEFINITE_REFUSAL',name,flush=True)
  if window+4*3600-time.time()<1200:break
  time.sleep(max(0,attempted+1200-time.time()))
 if not ep:print('NO_A100',flush=True);return 2
 cut=created+0.3*3600/RATE-35;hard=created+0.3*3600/RATE
 print('OWNED_ENDPOINT',ep,'CUT',cut,flush=True)
 verified={};acks=[];result='unconfirmed';ka=False
 def bounded(args,t=35):
  if time.time()>=cut:raise TimeoutError('CU deadline')
  return cli(args,max(.1,min(t,cut-time.time())))
 def upload(src,n):return retry('upload '+n,lambda:ok(bounded(['upload',str(src),'/content/'+n],55)),cut)
 def remote(code):
  f=d/('exec_'+uuid.uuid4().hex+'.py');f.write_text("import sys;sys.path.insert(0,'/content')\nimport remote_diag as io\n"+code+'\n')
  return retry('exec',lambda:ok(bounded(['exec','-f',str(f)],45)),cut)
 def probe():
  reply=remote("print('DIAG_PROBE '+io.json.dumps(io.probe(io.C)),flush=True)")
  rows=[s[len('DIAG_PROBE '):] for s in reply.splitlines() if s.startswith('DIAG_PROBE ')]
  if len(rows)!=1:raise OSError('probe absent')
  return json.loads(rows[0])
 def download(n):return retry('download '+n,lambda:ok(bounded(['download','/content/diag/out/'+n,str(out/(n+'.partial'))],50)),cut)
 def collect():
  while time.time()<cut:
   try:
    for n,info in probe().items():
     if n in verified:continue
     if not re.fullmatch(r'[\w.-]+',n):raise ValueError('unsafe output')
     for item in (n,n+'.sha256'):download(item)
     h=sha(out/(n+'.partial'))
     if h!=info['sha'] or h!=(out/(n+'.sha256.partial')).read_text().strip() or (out/(n+'.partial')).stat().st_size!=info['size']:raise OSError('hash/size '+n)
     for item in (n,n+'.sha256'):(out/(item+'.partial')).replace(out/item)
     verified[n]=h;print('VERIFIED',n,h,flush=True)
    if len(acks)<len(CASES):
     label=CASES[len(acks)];hn=label+'_handoff.json'
     if hn in verified:
      hashes=json.loads((out/hn).read_text())['sha256']
      if set(hashes)<=set(verified) and all(verified[k]==v for k,v in hashes.items()):
       ackfile=d/(label+'.ack.pending');ackfile.write_text(json.dumps(hashes));upload(ackfile,ackfile.name);remote(f'io.ack(io.C,{label!r})');acks.append(label);print('ACK',label,flush=True)
    if 'run.failed' in verified:return 'failed'
    if 'run.done' in verified:return 'done' if json.loads((out/'run.done').read_text())['verified_cases']==list(CASES) and acks==list(CASES) else 'failed'
   except (OSError,TimeoutError) as e:print('RETRY_NO_STOP',repr(e),flush=True)
   time.sleep(min(4,max(0,cut-time.time())))
  return 'deadline'
 try:
  machine=ok(bounded(['exec','-f',str(R/'machine.py')],40));rows=[s[len('GPU_MACHINE '):] for s in machine.splitlines() if s.startswith('GPU_MACHINE ')]
  if len(rows)!=1:raise RuntimeError('machine probe absent')
  info=json.loads(rows[0]);m=re.fullmatch(r'([^,]+),\s*(\d+),\s*(\d+)',info['stdout'].strip()) if info['rc']==0 else None
  if not m or 'A100' not in m[1] or int(m[3])<12000:raise ValueError('not A100/free memory')
  print('MACHINE',m.groups(),flush=True)
  budget=d/'diag_budget.json';budget.write_text(json.dumps({'mode':'production','work_deadline':cut})+'\n')
  for n in PAYLOAD:upload(budget if n=='diag_budget.json' else R/n,n)
  receipt=d/'diag_upload.json';receipt.write_text(json.dumps({n:sha(budget if n=='diag_budget.json' else R/n) for n in PAYLOAD}));upload(receipt,receipt.name)
  # One build+compile (120 s), two 1000-step cases (90 s each),
  # evidence/ACK (90 s); stop reserve 75 s is already excluded in cut.
  print('PRELAUNCH_MARGIN_S',cut-time.time()-(45+2*40+20),flush=True)
  if cut-time.time()<=45+2*40+20:raise TimeoutError('budget cannot fit')
  print('LAUNCH_REPLY',remote('io.launch(io.C)'),flush=True)
  kcmd=[str(pathlib.Path.home()/'bin/colab-keepalive'),'--config',str(cfg),'-s',name,'--log','/content/diag.log','--until-marker','/content/diag/out/run.done','--max-hours','1','--expect-hours','1','--no-remind','--final-pull','/content/diag/out/*.csv:'+str(d/'final'),'--final-pull','/content/diag/out/*.log:'+str(d/'final'),'--final-pull','/content/diag/out/*.sha256:'+str(d/'final'),'--detach']
  kr,ko=raw(kcmd,45);ka=kr==0;print('KEEPALIVE',kr,ko,flush=True)
  if not ka:raise OSError('keepalive start failed')
  result=collect()
 except Exception as e:
  print('CONTROLLER_EXCEPTION',repr(e),flush=True)
  if time.time()<cut:result=collect()
 finally:
  if result not in ('done','failed','deadline') and time.time()<cut:result=collect()
  if result not in ('done','failed','deadline'):raise RuntimeError('no permitted stop')
  print('STOP_REASON',result,flush=True)
  released=False
  for _ in range(3):
   print('STOP',cli(['stop'],max(.1,min(35,hard-time.time()))),flush=True)
   s,v=raw(BASE+['sessions'],max(.1,min(20,hard-time.time())));released=s==0 and ep not in v
   if released:break
  print('ENDPOINT',ep,'released',released,'CU_ESTIMATE',((time.time()-created)*RATE/3600 if released else None),flush=True)
  if ka:print('KEEPALIVE_STOP',raw(['systemctl','--user','stop','colab-keepalive-'+name]),flush=True)
  print('ORPHANS',raw([str(pathlib.Path.home()/'bin/colab-orphans')],35),flush=True)
 return 0 if result=='done' and released else 2
if __name__=='__main__':
 if '--authorized-run' not in sys.argv:raise SystemExit('inert without authorization')
 sys.exit(main())
