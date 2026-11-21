#!/usr/bin/env python3
"""Check exact 00/12 UTC S3 objects for landfall minus 24/48/72 h."""
import csv,io,xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
P=Path(__file__).resolve().parent
rows=list(csv.DictReader((P/'events.csv').open()))
def check(row,model,h):
 t=datetime.fromisoformat(row['landfall_utc'])-timedelta(hours=h)
 init=t.replace(hour=12 if t.hour>=12 else 0,minute=0,second=0,microsecond=0)
 prefix=f'{model}/{init.year}/{init:%m%d}/{model}_{init:%Y%m%d%H}_f000_f240_06.nc'
 u='https://noaa-oar-mlwp-data.s3.amazonaws.com/?'+urlencode({'list-type':'2','prefix':prefix,'max-keys':'1'})
 try:
  x=ET.fromstring(urlopen(u,timeout=35).read());present=int(x.findtext('{*}KeyCount','0'))>0
  return {'event':row['name'],'atcf_id':row['atcf_id'],'model':model,'lead_target_h':h,'init_utc':init.isoformat(),'actual_lead_h':round((datetime.fromisoformat(row['landfall_utc'])-init).total_seconds()/3600,2),'object_present':present,'object_key':prefix if present else '', 's3_listing_url':u}
 except Exception as ex:return {'event':row['name'],'model':model,'lead_target_h':h,'object_present':'ERROR','error':str(ex)}
with ThreadPoolExecutor(max_workers=6) as pool:
 fs=[pool.submit(check,r,m,h) for r in rows for m in ('PANG_v100_GFS','FOUR_v200_GFS','GRAP_v100_GFS') for h in (24,48,72)]
 out=[f.result() for f in as_completed(fs)]
out.sort(key=lambda x:(x['event'],x['model'],x['lead_target_h']))
with (P/'aiwp_object_coverage.csv').open('w',newline='') as f:
 keys=sorted(set().union(*(r.keys() for r in out)));w=csv.DictWriter(f,keys);w.writeheader();w.writerows(out)
print('counts',len(out),'present',sum(x['object_present'] is True for x in out),'errors',sum(x['object_present']=='ERROR' for x in out))
for r in rows:
 for m in ('PANG_v100_GFS','FOUR_v200_GFS','GRAP_v100_GFS'):
  matches=[x for x in out if x['event']==r['name'] and x['model']==m]
  print(r['name'],m,[x['object_present'] for x in matches])
