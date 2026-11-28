"""Idempotent Colab worker launch, evidence probe and ACK."""
import hashlib,json,pathlib,subprocess,sys
C=pathlib.Path('/content');LABELS=('d1','d2')
def probe(c):
 o=c/'diag/out';ready={}
 for s in sorted(o.glob('*.sha256')):
  p=o/s.name[:-7]
  if p.is_file():ready[p.name]={'sha':s.read_text().strip(),'size':p.stat().st_size}
 return ready
def ack(c,label):
 if label not in LABELS:raise ValueError(label)
 (c/(label+'.ack.pending')).replace(c/'diag/out'/(label+'.ack.json'))
def launch(c):
 mark=c/'diag.launch';receipt=c/'diag_upload.json'
 for n,h in json.loads(receipt.read_text()).items():
  if pathlib.Path(n).name!=n or hashlib.sha256((c/n).read_bytes()).hexdigest()!=h:raise ValueError('upload '+n)
 if json.loads((c/'diag_budget.json').read_text())['mode']!='production':raise ValueError('not production')
 if mark.exists():print('ALREADY_LAUNCHED',mark.read_text(),flush=True);return
 with mark.open('x') as f,(c/'diag.log').open('x') as log:
  p=subprocess.Popen([sys.executable,str(c/'worker_diag.py')],cwd=c,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
  f.write(str(p.pid));print('LAUNCHED',p.pid,flush=True)
