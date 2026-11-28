from pathlib import Path
import os, json
c=Path('/content')
for n in ('a170_2_pair_pilot.log','a170_2_pair_pilot.json','a170_2_pair_pilot.done','a170_2_pair_pilot.failed','a170_2_checkpoint.tar.gz'):
 p=c/n
 print(n, p.exists(), p.stat().st_size if p.exists() else 0)
 if p.exists() and p.suffix in ('.log','.json','.failed'):
  print(p.read_text()[-3000:])
print('processes')
os.system("ps -eo pid,stat,etime,args | grep -E 'pair_pilot|openfast' | grep -v grep")
