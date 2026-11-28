#!/usr/bin/env python3
"""Batch s2b frozen tracker, one attempt per event/model/lead; manifest persists."""
import csv,json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
src=HERE.parent.parent/'events_verified.csv'
events=[x['name'] for x in csv.DictReader(src.open())]
manifest=HERE/'track_manifest.jsonl'
for model,lead in [('PANG',48),('PANG',24),('FOUR',48),('GRAP',48)]:
 for event in events:
  out=HERE/f'track_{event.lower()}_{model.lower()}_{lead}.json'
  if out.exists():
   print('EXISTING',model,lead,event,flush=True);continue
  print('BEGIN',model,lead,event,flush=True)
  started=time.monotonic()
  try:
   p=subprocess.run([sys.executable,str(HERE/'ai_tracker_s2b.py'),event,str(lead),model],stdout=HERE.open('a') if False else subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1000)
   record={'model':model,'lead':lead,'event':event,'code':p.returncode,'elapsed_s':time.monotonic()-started,'output_last':p.stdout[-2500:]}
  except subprocess.TimeoutExpired as ex:
   record={'model':model,'lead':lead,'event':event,'code':'timeout','elapsed_s':time.monotonic()-started,'output_last':str(ex)[-1000:]}
  with manifest.open('a') as f:f.write(json.dumps(record)+'\n')
  print('END',record,flush=True)
