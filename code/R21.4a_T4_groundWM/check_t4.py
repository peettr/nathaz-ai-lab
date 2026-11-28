from pathlib import Path
import hashlib,os,json
out=Path('/content/t4_out')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
print('T4_PROBE done', (out/'run.done').exists(),'failed',(out/'run.failed').exists(),'smoke',(out/'smoke_ready').exists(),'baseline',(out/'baseline_gate.ack').exists())
for p in sorted(out.glob('*_thin.npz')):print('THIN',p.name,p.stat().st_size,sha(p),'ACKED', (out/(p.stem+'_verified.ack')).exists())
log=Path('/content/t4.log')
if log.exists():print('LOGTAIL',' | '.join(log.read_text(errors='replace').splitlines()[-10:])[-2000:])
if (out/'run.failed').exists():print('FAIL', (out/'run.failed').read_text()[-1500:])
