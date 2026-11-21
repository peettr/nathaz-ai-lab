"""Idempotent remote T15 launch, compact evidence probe and host ACK."""
import hashlib,json,pathlib,re,subprocess,sys
C=pathlib.Path('/content')
LABELS=('E3_native','WM_s107','WM_s108','WM_s109','K3_s107')
def probe(c):
 o=c/'t15/out';ready={}
 for s in sorted(o.glob('*.sha256')):
  p=o/s.name[:-7]
  if p.is_file():ready[p.name]={'sha':s.read_text().strip(),'size':p.stat().st_size}
 return ready
def ack(c,label):
 if label not in LABELS:raise ValueError(label)
 (c/(label+'.ack.pending')).replace(c/'t15/out'/(label+'.ack.json'))
def launch(c):
 mark=c/'t15.launch';receipt=c/'t15_upload.json'
 if not receipt.is_file():raise ValueError('no uploaded manifest')
 for n,h in json.loads(receipt.read_text()).items():
  if pathlib.Path(n).name!=n or hashlib.sha256((c/n).read_bytes()).hexdigest()!=h:raise ValueError('upload hash '+n)
 if json.loads((c/'t15_budget.json').read_text())['mode']!='production':raise ValueError('production only')
 if mark.exists():
  pid=mark.read_text().strip()
  if not pid:raise OSError('launch marker exists but PID unwritten')
  print('ALREADY_LAUNCHED',pid,flush=True);return
 with mark.open('x') as f,(c/'t15.log').open('x') as log:
  p=subprocess.Popen([sys.executable,str(c/'worker_full.py')],cwd=c,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
  f.write(str(p.pid));print('LAUNCHED',p.pid,flush=True)
