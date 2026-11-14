from pathlib import Path
for p in ['/content/luw_wp1_precision/FP32_head/run.log','/content/luw_wp1_precision/FP32_first/run.log']:
 q=Path(p);print(p,q.stat().st_size, q.read_text(errors='replace')[-4000:])
