from pathlib import Path
import subprocess
r=Path('/content/r234c_gc37_60b2bf75')
for n in ('infer_60b2bf75.log','wps_p24_snowfix.log','WPS_2020060806_REPORT.json'):
 p=r/n
 print(n,p.exists(),p.stat().st_size if p.exists() else None)
 if p.exists() and p.suffix=='.log':print('\n'.join(p.read_text(errors='replace').splitlines()[-14:]))
for p in sorted(r.glob('WPS_*REPORT.json')): print('REPORT',p.name,p.stat().st_size)
for p in sorted(r.glob('SOIL_FILL*')): print('FILL',p.name,p.stat().st_size)
print(subprocess.run(['ps','-eo','pid,stat,etime,args'],capture_output=True,text=True).stdout.split('PID STAT ELAPSED COMMAND')[-1][-5000:])
