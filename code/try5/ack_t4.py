from pathlib import Path
import os,hashlib
out=Path('/content/t4_out');kind=os.environ['T4_ACK_KIND'];value=os.environ['T4_ACK_VALUE']
assert kind in ('smoke','baseline_gate','off_s107','wm_s107','wm_s108','wm_s109')
if kind=='smoke':
 assert (out/'smoke_ready').exists() and value=='ok';dest=out/'smoke_verified.ack'
elif kind=='baseline_gate':
 assert (out/'off_s107_verified.ack').exists() and value=='PASS';dest=out/'baseline_gate.ack'
else:
 p=out/f'{kind}_thin.npz';assert p.exists()
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 assert h.hexdigest()==value
 dest=out/f'{kind}_verified.ack'
if dest.exists():assert dest.read_text().strip()==value
else:
 with dest.open('x') as f:f.write(value+'\n')
print('T4_ACK',kind,value)
