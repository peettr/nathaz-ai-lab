#!/usr/bin/env python3
"""Run the actual T11 worker in PAYLOAD-only /content emulation."""
import hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile,time
import controller as c
import remote_io as io
R=pathlib.Path(__file__).resolve().parent

def main():
 with tempfile.TemporaryDirectory(prefix='t11-dry-',dir=os.environ.get('TMPDIR')) as temp:
  content=pathlib.Path(temp)/'content';content.mkdir();out=R/'local_dry_retry4';out.mkdir(exist_ok=False)
  for n in c.PAYLOAD:
   if n=='t11_budget.json':(content/n).write_text(json.dumps({'mode':'fixture','work_deadline':time.time()+900}))
   else:shutil.copyfile(R/n,content/n)
  assert {p.name for p in content.iterdir()}==set(c.PAYLOAD)
  print('PAYLOAD_ONLY',sorted(c.PAYLOAD),flush=True)
  with (out/'worker.log').open('x') as log:
   p=subprocess.Popen([sys.executable,str(content/'worker.py'),'--content',str(content),'--stub',str(R/'dry_stub.py')],cwd=content,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
   try:
    def download(n,dest):shutil.copyfile(content/'t11/out'/n,dest)
    def publish(label,hashes):
     (content/(label+'.ack.pending')).write_text(json.dumps(hashes));io.ack(content,label)
    result=c.collect(out,lambda:io.probe(content),download,publish,time.time()+850,'fixture')
    rc=p.wait(timeout=8)
   finally:
    if p.poll() is None:p.terminate();p.wait(timeout=8)
  print((out/'worker.log').read_text()[-4000:],flush=True)
  print('DRY_RESULT',result,rc,flush=True)
  assert result=='done' and rc==0
  for label in c.CASES:
   assert len(json.loads((out/(label+'_points80.json')).read_text())['rows'])==80
   assert len(json.loads((out/(label+'_profile.json')).read_text())['profile'])==18
   assert (out/(label+'_upstream_slice.npz')).stat().st_size>100
  assert all(c.sha(p.with_name(p.name[:-7]))==p.read_text().strip() for p in out.glob('*.sha256'))
 print('REAL_WORKER_PASS: two cases, 80 points, 18 profile stations each, 2 upstream slices, SHA and ACK; no GPU',flush=True)
if __name__=='__main__':main()
