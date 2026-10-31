"""Resume missing station-season keys only, append to immutable first-pass JSONL."""
import json,os,sys,time,traceback
from pathlib import Path
sys.path.insert(0,'/content')
from audit_colab import run,SIDS,ROOT
p=ROOT/'season_audit.jsonl';a=[json.loads(z) for z in p.read_text().splitlines()];done={(x['station'][1:],int(x['season'][:4])) for x in a}
missing=[(s,y) for y in range(2000,2024) for s in SIDS if (s,y) not in done]
print('MISSING',len(missing),missing,flush=True)
errs=[]
for sid,y in missing:
 for attempt in range(3):
  try:
   row=run(sid,y)
   with p.open('a') as f:f.write(json.dumps(row,separators=(',',':'))+'\n');f.flush();os.fsync(f.fileno())
   print('REPAIRED',sid,y,row['raw_rows'],flush=True)
   break
  except Exception as e:
   print('RETRY',sid,y,attempt,repr(e),flush=True)
   if attempt==2:errs.append({'station':sid,'year':y,'error':repr(e)})
   time.sleep((attempt+1)*5)
result={'expected':360,'total':len(done)+len(missing)-len(errs),'failed':errs}
(ROOT/'repair.exit.json').open('x').write(json.dumps(result))
print('REPAIR_EXIT',result,flush=True)
