from pathlib import Path
import os, subprocess, time
r=Path('/content/m6')
for n in ['score.log','score.exit','score.done','test_predictions_delay4.parquet','test_predictions_delay3.parquet','test_predictions_delay6.parquet']:
 p=r/n
 print(n, 'missing' if not p.exists() else (p.stat().st_size,round(time.time()-p.stat().st_mtime,1),p.read_text()[-250:] if n.endswith(('.log','.exit')) else ''))
for p in sorted((r/'output_final').glob('*')):
 print('OUT',p.name,p.stat().st_size,round(time.time()-p.stat().st_mtime,1))
print(subprocess.run(['ps','-eo','pid,etime,%cpu,%mem,state,args'],capture_output=True,text=True).stdout[-5000:])
