from pathlib import Path
import hashlib,subprocess
b=Path('/content')
p=b/'try13_shear_wall.csv'
print('SHEAR_PROBE lock', (b/'try13_shear.launch.lock').exists(),'done',(b/'try13_shear.done').exists(),'failed',(b/'try13_shear.failed').exists(),flush=True)
print('PROCESSES',subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True).stdout[-2500:],flush=True)
if p.exists():
 print('SHEAR_SHA',hashlib.sha256(p.read_bytes()).hexdigest(),'bytes',p.stat().st_size,flush=True)
