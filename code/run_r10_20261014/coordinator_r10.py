"""Continue the four-case sequence, never start a variant twice."""
from pathlib import Path
import subprocess,time,traceback
r=Path('/content/luw-aij-r10')
with (r/'coordinator.lock').open('x') as f:f.write('r10 sequence\n')
try:
 for v in 'abcd':
  marker=r/f'solver_{v}.exit'
  if v!='a':
   assert not (r/f'solver_{v}.lock').exists(),v
   p=subprocess.run(['python3',f'/content/launch_{v}_r10.py'],capture_output=True,text=True)
   print('LAUNCH',v,p.returncode,p.stdout,p.stderr,flush=True);assert p.returncode==0
  while not marker.exists():
   assert (r/f'solver_{v}.lock').exists()
   time.sleep(30)
  print('EXIT',v,marker.read_text(),flush=True)
  assert marker.read_text().startswith('exit=0'),v
  with (r/f'extract_{v}.log').open('w') as f:
   p=subprocess.run(['python3',f'/content/extract_{v}_r10.py'],stdout=f,stderr=subprocess.STDOUT)
  print('EXTRACT',v,p.returncode,flush=True);assert p.returncode==0,(v,(r/f'extract_{v}.log').read_text()[-1500:])
 (r/'coordinator.done').write_text('abcd exit=0 and extracted\n')
except Exception:
 (r/'coordinator.error').write_text(traceback.format_exc())
 print(traceback.format_exc(),flush=True)
