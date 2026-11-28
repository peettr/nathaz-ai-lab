#!/usr/bin/env python3.10
"""PAYLOAD-only T15 full-chain dry run; inject one timeout per I/O class."""
import hashlib,importlib.util,json,os,pathlib,shutil,subprocess,sys,time
import numpy as np
R=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def once(kind,fn):
 triggered=[False]
 def act():
  if not triggered[0]:
   triggered[0]=True;print('INJECT_TIMEOUT',kind,flush=True);raise OSError('timeout')
  return fn()
 return act,triggered
def retry(kind,fn):
 for attempt in range(5):
  try:return fn()
  except (OSError,TimeoutError) as e:
   print('STEP_RETRY',kind,attempt+1,repr(e),flush=True)
   if attempt==4:raise
   time.sleep(.02)
def main():
 root=R/'dry_e3_sandbox_v5';root.mkdir(exist_ok=False);content=root/'content';content.mkdir()
 payload=('t15_stage.tar.gz','t15_manifest.json','worker_full.py','remote_worker_run2.py','assert_e3.py','t15_budget.json')
 created=time.time();cut=created+1.5*3600/5.4-180
 budget=root/'fixture_budget.json';budget.write_text(json.dumps({'mode':'fixture','work_deadline':cut})+'\n')
 print('PRODUCTION_CUT created',created,'cut',cut,'total_available_s',cut-created,'reserve_s',360,flush=True)
 def upload():
  for n in payload:
   src=budget if n=='t15_budget.json' else R/n
   shutil.copyfile(src,content/n)
 act,u=once('upload',upload);retry('upload',act)
 if {p.name for p in content.iterdir()}!=set(payload):raise ValueError('PAYLOAD-only violation')
 print('PAYLOAD_ONLY',payload,flush=True)
 stub=R/'stub_full.py';log=root/'worker.log'
 with log.open('x') as f:p=subprocess.Popen([sys.executable,str(content/'worker_full.py'),'--content',str(content),'--stub',str(stub)],cwd=content,stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
 try:
  exec_,e=once('exec',lambda:print('EXEC_WORKER_ALREADY_STARTED_EXCLUSIVELY',p.pid,flush=True))
  retry('exec',exec_)
  probe,pr=once('probe',lambda: {q.name[:-7]:q.read_text().strip() for q in (content/'t15/out').glob('*.sha256')})
  def get(name,dst):shutil.copyfile(content/'t15/out'/name,dst)
  first=[False]
  def download(name,dst):
   if not first[0]:
    first[0]=True;print('INJECT_TIMEOUT download',flush=True);raise OSError('timeout')
   return get(name,dst)
  local=root/'verified';local.mkdir()
  for label,_,_ in (('E3_native','e3',107),):
   hand=label+'_handoff.json';end=time.time()+1800
   while hand not in retry('probe',probe):
    if p.poll() is not None:raise RuntimeError('worker exit before '+label+'; see worker.log')
    if time.time()>end:raise TimeoutError(label)
    time.sleep(.1)
   retry('download',lambda:download(hand,local/hand))
   if sha(local/hand)!=sha(content/'t15/out'/hand):raise ValueError('handoff sha')
   hashes=json.loads((local/hand).read_text())['sha256']
   if label=='E3_native' and label+'_gate.json' not in hashes:raise ValueError('missing E3 gate')
   for n,h in hashes.items():
    retry('download',lambda n=n:download(n,local/n))
    retry('download',lambda n=n:download(n+'.sha256',local/(n+'.sha256')))
    if sha(local/n)!=h or (local/(n+'.sha256')).read_text().strip()!=h:raise ValueError('file SHA '+n)
   (content/'t15/out'/(label+'.ack.json')).write_text(json.dumps(hashes))
   print('ACK_SHA_OK',label,len(hashes),flush=True)
  if p.wait(timeout=60):raise RuntimeError('worker exit; see worker.log')
  text=log.read_text()
  import re
  m=re.search(r'E3_BUDGET remaining_s ([0-9.]+) reserve_s ([0-9]+) margin_s ([0-9.]+)',text)
  if not m or float(m[3])<=0:raise AssertionError('production E3 post-compile margin not positive')
  print('POST_COMPILE_MARGIN_S',m[3],'ASSERT_POSITIVE',flush=True)
  if not (content/'t15/out/run.done').is_file():raise RuntimeError('missing done')
  if not all(x[0] for x in (u,e,pr)) or not first[0]:raise RuntimeError('timeout injection incomplete')
  print('E3_CHAIN_PASS 4 compile variants plus E3 gate; four timeout classes; real worker/build, stub solver; NO GPU',flush=True)
 finally:
  if p.poll() is None:p.terminate();p.wait(timeout=10)
if __name__=='__main__':main()
