from pathlib import Path
import subprocess
p=Path('/content/a3_b2_1014')
print('log',(p/'gate_fix2.log').read_text(errors='replace')[-2400:]); print('metrics',(p/'gate_metrics.jsonl').read_text()[-1800:] if (p/'gate_metrics.jsonl').exists() else 'none')
for x in sorted((p/'gate_runs').glob('gate16_s112_FB_attempt3/*')):
 if x.name=='openfast.log':print('openfast',x.read_text(errors='replace')[-1000:]);
print('process',subprocess.run(['ps','-eo','pid,etime,cmd'],capture_output=True,text=True).stdout[-2200:])
