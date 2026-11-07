"""Data transfer only: fetch IEM/NCEI source responses to approved TACC /work.
No statistical processing or model computation on the login node. Resume skips files
only after a nonzero byte count; receipts include size and source URL.
"""
import json,urllib.request,gzip,hashlib,time,sys,os
from pathlib import Path
root=Path('/work2/04448/[用户]/超算/AI_Weather/site_stage_qc/raw');root.mkdir(parents=True,exist_ok=True)
manifest=Path('/work2/04448/[用户]/超算/AI_Weather/site_stage_qc/raw_manifest.jsonl')
items=[];seen=set()
for line in manifest.open():
 r=json.loads(line);st=r['station'];y=r['season_year']
 for kind,u in [('iem',r['iem_url'])]+[('isd',z) for z in r['isd_urls']]:
  if u in seen:continue
  seen.add(u);name=f'{st}_{y}' if kind=='iem' else hashlib.sha256(u.encode()).hexdigest()[:16]
  items.append((kind,name,u))
receipts=root/'receipts.jsonl';failed=root/'failures.jsonl'
for i,(kind,name,u) in enumerate(items,1):
 dest=root/kind/(name+'.gz');dest.parent.mkdir(exist_ok=True)
 if dest.exists() and dest.stat().st_size>0:continue
 error=None
 for attempt in range(3):
  tmp=dest.with_suffix('.partial')
  try:
   req=urllib.request.Request(u,headers={'User-Agent':'PETW-AIWeather-QC-source-archive/1.0'})
   with urllib.request.urlopen(req,timeout=120) as inp,gzip.open(tmp,'wb',compresslevel=1) as out:
    while True:
     b=inp.read(1024*1024)
     if not b:break
     out.write(b)
   if tmp.stat().st_size==0:raise ValueError('empty')
   os.replace(tmp,dest)
   with receipts.open('a') as f:f.write(json.dumps({'kind':kind,'file':str(dest),'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'url':u})+'\n')
   error=None;break
  except Exception as ex:error=repr(ex);time.sleep(2*(attempt+1))
 if error:
  with failed.open('a') as f:f.write(json.dumps({'kind':kind,'name':name,'error':error,'url':u})+'\n')
 if i%25==0:print('TRANSFER',i,len(items),flush=True)
print('DONE',len(items),'FAIL',sum(1 for _ in failed.open()) if failed.exists() else 0,flush=True)
