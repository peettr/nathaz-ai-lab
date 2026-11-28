"""Stage one-minute source archives on TACC /work; transfer only."""
import json,urllib.request,gzip,hashlib,time,os
from pathlib import Path
base=Path('/work2/04448/[用户]/超算/AI_Weather/site_stage_qc');root=base/'raw/minute';root.mkdir(parents=True,exist_ok=True)
manifest=base/'minute_raw_manifest.jsonl';receipts=base/'raw/minute_receipts.jsonl';failures=base/'raw/minute_failures.jsonl'
for i,line in enumerate(manifest.open(),1):
 r=json.loads(line);dst=root/f"{r['station']}_{r['season_year']}.gz";url=r['minute_url']
 if dst.exists() and dst.stat().st_size:continue
 err=None
 for j in range(3):
  try:
   tmp=dst.with_suffix('.partial')
   req=urllib.request.Request(url,headers={'User-Agent':'PETW-AIWeather-QC-source-archive/1.0'})
   with urllib.request.urlopen(req,timeout=180) as inp,gzip.open(tmp,'wb',compresslevel=1) as out:
    while True:
     z=inp.read(1024*1024)
     if not z:break
     out.write(z)
   if tmp.stat().st_size==0:raise ValueError('empty')
   os.replace(tmp,dst)
   with receipts.open('a') as f:f.write(json.dumps({'file':str(dst),'bytes':dst.stat().st_size,'sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'url':url})+'\n')
   err=None;break
  except Exception as ex:err=repr(ex);time.sleep(2*(j+1))
 if err:
  with failures.open('a') as f:f.write(json.dumps({'station':r['station'],'season_year':r['season_year'],'error':err,'url':url})+'\n')
 if i%20==0:print('MINUTE_ARCHIVE',i,flush=True)
print('DONE',i,'FAIL',sum(1 for _ in failures.open()) if failures.exists() else 0,flush=True)
