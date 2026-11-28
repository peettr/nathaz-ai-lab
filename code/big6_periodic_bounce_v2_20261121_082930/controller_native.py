#!/usr/bin/env python3
"""T17 B A100 controller template. Inert pending native statistical producer."""
import argparse,hashlib,json,os,pathlib,re,subprocess,sys,time,uuid
R=pathlib.Path(__file__).resolve().parent;BASE=['colab','--auth','oauth2'];RATE=5.4
ALL_CASES=('bounce_s1','bounce_s2')
PAYLOAD=('worker_native.py','native_analysis.py','analyze_longspin.py','remote_B.py','assert_T17.py','t17b_stage.tar.gz','t17b_manifest.json','t17b_budget.json')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def raw(args,t=35):
 try:
  p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,stdin=subprocess.DEVNULL,timeout=t);return p.returncode,p.stdout
 except subprocess.TimeoutExpired:return 124,'CLI_TIMEOUT ambiguous'
def checked(pair):
 rc,out=pair
 if rc:raise OSError(out[-1500:])
 return out
def retry(kind,fn,deadline):
 for i in range(5):
  try:x=fn();print('STEP_OK',kind,i,flush=True);return x
  except (OSError,TimeoutError) as e:
   print('TRANSIENT',kind,i,repr(e),flush=True)
   if i==4 or time.time()>=deadline:raise
   time.sleep(min(30*2**i,max(0,deadline-time.time())))
def main():
 mode='production'
 if mode not in ('smoke','production'):raise ValueError('mode')
 cases=ALL_CASES
 seal=json.loads((R/'PREFLIGHT.ok').read_text())
 if any(sha(R/n)!=h for n,h in seal.items()):raise RuntimeError('seal mismatch')
 # Fail closed: stage A solver has no native producer for the frozen §3 statistics.
 if not (R/'NATIVE_PRODUCER_APPROVED.ok').is_file():raise RuntimeError('native producer preflight required')
 plan=json.loads((R/'SESSION_PLAN.json').read_text())
 if 2*plan['worst_case_solver_s']+plan['fixed_overhead_s']+180 >= 12.5*3600/RATE:
  raise RuntimeError('preallocation budget gate: first worst-case does not fit')
 before=checked(raw(BASE+['sessions']));window=time.time();ep=None
 (R/'.colab_owner').open('x').write('T17 B '+mode+'; researchos-uwind-luw; delegated by luw-claude\n')
 events=(R/'allocation_events.log').open('x',buffering=1);sys.stdout=events
 while time.time()-window<4*3600:
  name='luw-t17-a100-'+uuid.uuid4().hex[:8];d=R/('session_'+name);d.mkdir();cfg=d/'sessions.json';o=d/'evidence';o.mkdir()
  if name in before:raise RuntimeError('name collision')
  def cli(args,t=35):return raw(BASE+['--config',str(cfg),args[0],'-s',name]+args[1:],t)
  attempted=time.time();rc,msg=cli(['new','--gpu','A100'],100);print('ALLOC',name,rc,msg,flush=True)
  after=checked(raw(BASE+['sessions']));local=checked(raw(BASE+['--config',str(cfg),'sessions']))
  candidates=set(re.findall(r'gpu-a100-[a-z0-9-]+','\n'.join(x for x in local.splitlines() if name in x)+'\n'+msg))
  owned={x for x in candidates if x in after and x not in before}
  if len(owned)==1:ep=owned.pop();created=attempted;break
  if rc==0 or not re.search('503|412|Service Unavailable|Allocation refused|precondition failed',msg,re.I) or name in after or candidates:
   raise RuntimeError('ambiguous allocation; no duplicate')
  print('DEFINITE_REFUSAL',name,flush=True)
  if window+4*3600-time.time()<1200:break
  time.sleep(max(0,attempted+1200-time.time()))
 if not ep:print('NO_A100',flush=True);return 2
 cap=12.5
 cut=created+cap*3600/RATE-90;hard=created+cap*3600/RATE
 print('OWNED_ENDPOINT',ep,'CUT',cut,flush=True)
 verified={};acks=[];result='unconfirmed';ka=False
 def bounded(args,t=35):
  if time.time()>=cut:raise TimeoutError('CU deadline')
  return cli(args,max(.1,min(t,cut-time.time())))
 def upload(src,n):return retry('upload '+n,lambda:checked(bounded(['upload',str(src),'/content/'+n],60)),cut)
 def remote(code):
  f=d/('exec_'+uuid.uuid4().hex+'.py');f.write_text("import sys;sys.path.insert(0,'/content')\nimport remote_B as io\n"+code+'\n')
  return retry('exec',lambda:checked(bounded(['exec','-f',str(f)],45)),cut)
 def probe():
  out=remote("print('T17_PROBE '+io.json.dumps(io.probe(io.C)),flush=True)")
  rows=[x[len('T17_PROBE '):] for x in out.splitlines() if x.startswith('T17_PROBE ')]
  if len(rows)!=1:raise OSError('probe absent')
  return json.loads(rows[0])
 def download(n):return retry('download '+n,lambda:checked(bounded(['download','/content/t17b/out/'+n,str(o/(n+'.partial'))],55)),cut)
 def ack(label,hashes):
  p=d/(label+'.ack.pending');p.write_text(json.dumps(hashes));upload(p,p.name)
  remote(f'io.ack(io.C,{label!r})')
 def collect():
  while time.time()<cut:
   try:
    for n,info in probe().items():
     if n in verified:continue
     if not re.fullmatch(r'[\w.-]+',n):raise ValueError('unsafe output')
     for item in (n,n+'.sha256'):download(item)
     h=sha(o/(n+'.partial'))
     if h!=info['sha'] or h!=(o/(n+'.sha256.partial')).read_text().strip() or (o/(n+'.partial')).stat().st_size!=info['size']:raise OSError('hash/size '+n)
     for item in (n,n+'.sha256'):(o/(item+'.partial')).replace(o/item)
     verified[n]=h;print('VERIFIED',n,h,flush=True)
    if len(acks)<len(cases):
     label=cases[len(acks)];hn=label+'_handoff.json'
     if hn in verified:
      hashes=json.loads((o/hn).read_text())['sha256']
      if set(hashes)<=set(verified) and all(verified[k]==v for k,v in hashes.items()):
       # Only delivery/contract is checked here. The full scientific verdict is
       # read from T17_result.json after six paired cases, never from stub data.
       ack(label,hashes);acks.append(label);print('ACK',label,flush=True)
    if 'run.failed' in verified:return 'failed'
    if 'run.done' in verified:
     done=json.loads((o/'run.done').read_text());expected=done['verified']
     if expected==list(cases)[:len(expected)] and acks==expected and all(x+'_case.json' in verified and x+'_windows.json' in verified for x in expected):
      return 'budget_stop' if done.get('budget_stop') else 'done'
     return 'failed'
   except (OSError,TimeoutError) as e:print('RETRY_NO_STOP',repr(e),flush=True)
   time.sleep(min(8,max(0,cut-time.time())))
  return 'deadline'
 try:
  machine=checked(bounded(['exec','-f',str(R/'machine.py')],40))
  rows=[x[len('GPU_MACHINE '):] for x in machine.splitlines() if x.startswith('GPU_MACHINE ')]
  if len(rows)!=1:raise RuntimeError('machine probe absent')
  info=json.loads(rows[0]);m=re.fullmatch(r'([^,]+),\s*(\d+),\s*(\d+)',info['stdout'].strip()) if info['rc']==0 else None
  if not m or 'A100' not in m[1] or int(m[3])<12000:raise ValueError('not A100/free memory')
  print('MACHINE',m.groups(),flush=True)
  plan=json.loads((R/'SESSION_PLAN.json').read_text())
  budget=d/'t17b_budget.json';budget.write_text(json.dumps({'mode':mode,'work_deadline':cut,'steps_per_T':plan['steps_per_T'],'steps_per_second':plan['steps_per_second'],'per_case_overhead_s':plan['per_case_overhead_s'],'teardown_s':90})+'\n')
  for n in PAYLOAD:upload(budget if n=='t17b_budget.json' else R/n,n)
  receipt=d/'t17b_upload.json';receipt.write_text(json.dumps({n:sha(budget if n=='t17b_budget.json' else R/n) for n in PAYLOAD}));upload(receipt,receipt.name)
  required=(2000/plan['steps_per_second']['t15']+90) if mode=='smoke' else plan['worst_case_solver_s']+plan['fixed_overhead_s']
  margin=cut-time.time()-required
  print('PRELAUNCH_MARGIN_S',margin,flush=True)
  if margin<=0:raise TimeoutError('budget cannot fit ordered cases')
  print('LAUNCH_REPLY',remote('io.launch(io.C)'),flush=True)
  ka_cmd=[str(pathlib.Path.home()/'bin/colab-keepalive'),'--config',str(cfg),'-s',name,'--log','/content/t17b.log','--until-marker','/content/t17b/out/run.done','--max-hours','4','--expect-hours','4','--no-remind','--pull','/content/t17b.log:'+str(d/'worker_progress.log'),'--final-pull','/content/t17b/out/*.json:'+str(d/'final'),'--final-pull','/content/t17b/out/*.csv:'+str(d/'final'),'--final-pull','/content/t17b/out/*.sha256:'+str(d/'final'),'--detach']
  rc,out=raw(ka_cmd,45);ka=rc==0;print('KEEPALIVE',rc,out,flush=True)
  if not ka:raise OSError('keepalive failure; continue probing')
  result=collect()
 except Exception as e:
  print('CONTROLLER_EXCEPTION',repr(e),flush=True)
  if time.time()<cut:result=collect()
 finally:
  if result not in ('done','failed','deadline','budget_stop') and time.time()<cut:result=collect()
  if result not in ('done','failed','deadline','budget_stop'):raise RuntimeError('no permitted stop condition')
  print('STOP_REASON',result,flush=True)
  released=False
  for _ in range(3):
   print('STOP',cli(['stop'],max(.1,min(35,hard-time.time()))),flush=True)
   s,v=raw(BASE+['sessions'],max(.1,min(20,hard-time.time())));released=s==0 and ep not in v
   if released:break
  print('ENDPOINT',ep,'released',released,'CU_ESTIMATE',((time.time()-created)*RATE/3600 if released else None),flush=True)
  if ka:print('KEEPALIVE_STOP',raw(['systemctl','--user','stop','colab-keepalive-'+name]),flush=True)
  print('ORPHANS',raw([str(pathlib.Path.home()/'bin/colab-orphans')],35),flush=True)
 return 0 if result in ('done','budget_stop') and released else 2
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--authorized-run',action='store_true');a=p.parse_args()
 if not a.authorized_run:raise SystemExit('inert without --authorized-run')
 sys.exit(main())
