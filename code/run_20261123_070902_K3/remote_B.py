"""T17 B idempotent launcher, SHA probe, and host ACK."""
import hashlib,json,pathlib,subprocess,sys
C=pathlib.Path('/content');LABELS=tuple(g+'_s1' for g in ('K1a','K1b','K2','K3a','K3b'))
def probe(c):
 o=c/'t17b/out';ready={}
 for s in sorted(o.glob('*.sha256')):
  p=o/s.name[:-7]
  if p.is_file():ready[p.name]={'sha':s.read_text().strip(),'size':p.stat().st_size}
 return ready
def ack(c,label):
 if label not in LABELS:raise ValueError(label)
 (c/(label+'.ack.pending')).replace(c/'t17b/out'/(label+'.ack.json'))
def launch(c):
 mark=c/'t17b.launch';receipt=c/'t17b_upload.json'
 if not receipt.is_file():raise ValueError('no receipt')
 for n,h in json.loads(receipt.read_text()).items():
  if pathlib.Path(n).name!=n or hashlib.sha256((c/n).read_bytes()).hexdigest()!=h:raise ValueError('upload '+n)
 if json.loads((c/'t17b_budget.json').read_text())['mode'] not in ('production','smoke'):raise ValueError('invalid mode')
 if mark.exists():print('ALREADY_LAUNCHED',mark.read_text(),flush=True);return
 with mark.open('x') as f,(c/'t17b.log').open('x') as log:
  p=subprocess.Popen([sys.executable,str(c/'worker_native.py')],cwd=c,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
  f.write(str(p.pid));print('LAUNCHED',p.pid,flush=True)
