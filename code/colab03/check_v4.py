from pathlib import Path
p=Path('/content/l264a100/texas')
for n in ('west_batch_v4.log','west_batch_v3.log','metric_batch_v3.log'):
 f=p/n;print(n,f.read_text(errors='replace')[-3000:] if f.exists() else '-',flush=True)
