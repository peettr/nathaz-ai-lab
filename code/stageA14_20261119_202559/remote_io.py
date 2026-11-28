"""T17 idempotent launcher, SHA probe, and host ACK."""
import hashlib,json,pathlib,subprocess,sys
C=pathlib.Path('/content');LABELS=('a3','a7','speed_bounce','speed_t4','speed_t15')
def probe(c):
 o=c/'t17/out';ready={}
 for s in sorted(o.glob('*.sha256')):
  p=o/s.name[:-7]
  if p.is_file():ready[p.name]={'sha':s.read_text().strip(),'size':p.stat().st_size}
 return ready
def ack(c,label):
 if label not in LABELS:raise ValueError(label)
 (c/(label+'.ack.pending')).replace(c/'t17/out'/(label+'.ack.json'))
def launch(c):
 mark=c/'t17.launch';receipt=c/'t17_upload.json'
 if not receipt.is_file():raise ValueError('no receipt')
 for n,h in json.loads(receipt.read_text()).items():
  if pathlib.Path(n).name!=n or hashlib.sha256((c/n).read_bytes()).hexdigest()!=h:raise ValueError('upload '+n)
 if json.loads((c/'t17_budget.json').read_text())['mode']!='production':raise ValueError('not production')
 if mark.exists():print('ALREADY_LAUNCHED',mark.read_text(),flush=True);return
 with mark.open('x') as f,(c/'t17.log').open('x') as log:
  p=subprocess.Popen([sys.executable,str(c/'worker_full.py')],cwd=c,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
  f.write(str(p.pid));print('LAUNCHED',p.pid,flush=True)
