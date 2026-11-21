#!/usr/bin/env python3.10
"""PAYLOAD-only T15 full-chain dry run; inject one timeout per I/O class."""
import hashlib,importlib.util,json,os,pathlib,shutil,subprocess,sys,time
import numpy as np
R=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('retries',R.parents[1]/'R21.4a_T13_smag_cs010/T13b_20261118_104520/controller.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
real_sleep=c.time.sleep;c.time.sleep=lambda s:real_sleep(min(s,0.02))
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
 root=R/'full_dry_sandbox_v3';root.mkdir(exist_ok=False);content=root/'content';content.mkdir()
 payload=('t15_stage.tar.gz','t15_manifest.json','worker_full.py','remote_worker_run2.py','t15_reference.npz','t15_budget.json')
 u,dims=(5,6,8,3),(5,6,8)
 ref=R/'fixture_reference_v3.npz'
 with ref.open('xb') as f:np.savez_compressed(f,u_avg=np.broadcast_to(np.array([.1,0.,0.],dtype='<f4'),u).copy(),fluid=np.ones(dims,dtype='<f4'))
 budget=R/'fixture_budget_v3.json';budget.write_text(json.dumps({'mode':'fixture','work_deadline':time.time()+3600})+'\n')
 def upload():
  for n in payload:
   src=ref if n=='t15_reference.npz' else budget if n=='t15_budget.json' else R/n
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
  for label,_,_ in (('E3_native','e3',107),('WM_s107','on',107),('WM_s108','on',108),('WM_s109','on',109),('K3_s107','k3',107)):
   hand=label+'_handoff.json';end=time.time()+1800
   while hand not in retry('probe',probe):
    if p.poll() is not None:raise RuntimeError('worker exit before '+label+'; see worker.log')
    if time.time()>end:raise TimeoutError(label)
    time.sleep(.1)
   retry('download',lambda:download(hand,local/hand))
   if sha(local/hand)!=sha(content/'t15/out'/hand):raise ValueError('handoff sha')
   hashes=json.loads((local/hand).read_text())['sha256']
   if label!='E3_native' and label+'_profile_upper.npz' not in hashes:raise ValueError('missing upper profile '+label)
   for n,h in hashes.items():
    retry('download',lambda n=n:download(n,local/n))
    retry('download',lambda n=n:download(n+'.sha256',local/(n+'.sha256')))
    if sha(local/n)!=h or (local/(n+'.sha256')).read_text().strip()!=h:raise ValueError('file SHA '+n)
   (content/'t15/out'/(label+'.ack.json')).write_text(json.dumps(hashes))
   print('ACK_SHA_OK',label,len(hashes),flush=True)
  if p.wait(timeout=60):raise RuntimeError('worker exit; see worker.log')
  if not (content/'t15/out/run.done').is_file():raise RuntimeError('missing done')
  if not all(x[0] for x in (u,e,pr)) or not first[0]:raise RuntimeError('timeout injection incomplete')
  print('E4_FULL_CHAIN_PASS 4 compile variants plus 5 ordered stages; four timeout classes; real worker/build, stub solver; NO GPU',flush=True)
 finally:
  if p.poll() is None:p.terminate();p.wait(timeout=10)
if __name__=='__main__':main()
