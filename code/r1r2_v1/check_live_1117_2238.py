from pathlib import Path
import subprocess, json, time
r=Path('/content/r234c_gc37_R1R2')
p=r/'worker_r1r2_v2.log'
print('log_tail', '\n'.join(p.read_text().splitlines()[-25:]) if p.exists() else 'ABSENT')
print('markers',[(f.name,f.stat().st_size) for f in r.glob('worker_r1r2_v2.*') if f.suffix in ('.done','.failed')])
print('forecast_summaries',[(f.parent.name,f.stat().st_size) for f in r.glob('forecast_*/summary.json')])
print('process',subprocess.run(['ps','-eo','pid,etime,stat,args'],text=True,capture_output=True).stdout.split('colab_worker_r1r2_v2.py')[0][-400:])
