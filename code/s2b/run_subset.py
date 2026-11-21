#!/usr/bin/env python3
import csv,json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
model=sys.argv[1];lead=int(sys.argv[2]);events=[r['name'] for r in csv.DictReader((HERE.parent.parent/'events_verified.csv').open())]
for event in events:
 out=HERE/f'track_{event.lower()}_{model.lower()}_{lead}.json'
 if out.exists():continue
 print('BEGIN',event,model,lead,flush=True);start=time.monotonic()
 try:
  p=subprocess.run([sys.executable,str(HERE/'ai_tracker_s2b.py'),event,str(lead),model],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1000)
  rec={'event':event,'model':model,'lead':lead,'code':p.returncode,'elapsed_s':time.monotonic()-start,'output_last':p.stdout[-1800:]}
 except subprocess.TimeoutExpired as ex:rec={'event':event,'model':model,'lead':lead,'code':'timeout','elapsed_s':time.monotonic()-start,'error':str(ex)}
 with (HERE/f'manifest_{model.lower()}_{lead}.jsonl').open('a') as f:f.write(json.dumps(rec)+'\n')
 print('END',rec,flush=True)
