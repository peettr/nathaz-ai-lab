import subprocess
from pathlib import Path
p=Path('/content/m6')
print(subprocess.run(['ps','-eo','pid,etime,%cpu,rss,args'],capture_output=True,text=True).stdout.splitlines()[-14:])
for name in ('main.csv','secondary_auc_delay4.csv','topk_delay4.csv'):
 q=p/'output_final'/name;print(name,q.stat().st_size if q.exists() else None)
