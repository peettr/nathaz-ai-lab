#!/usr/bin/env python3
"""Audit exact 48-h GFS and 2026 AIWP/OFCL objects without pairing observations."""
import csv,urllib.request,urllib.parse,gzip,xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timedelta
P=Path(__file__).resolve().parent;B=P.parent
E=list(csv.DictReader((P/'hourly_pool_150km.csv').open()));seen={r['event']:r for r in E}
results=[]
for name,r in seen.items():
 t=datetime.fromisoformat(r['landfall_utc']);before=t-timedelta(hours=48);init=before.replace(hour=12 if before.hour>=12 else 0,minute=0,second=0,microsecond=0)
 date=init.strftime('%Y%m%d');h=init.strftime('%H');g=f'https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{date}/{h}/atmos/gfs.t{h}z.pgrb2.0p50.f048.idx'
 try:
  text=urllib.request.urlopen(g,timeout=25).read().decode();ok=all(v in text for v in (':PRMSL:mean sea level:',':UGRD:10 m above ground:',':VGRD:10 m above ground:'));status='fields present' if ok else 'fields absent'
 except Exception as e:status=str(e)
 p=f'PANG_v100_GFS/{init.year}/{init:%m%d}/PANG_v100_GFS_{init:%Y%m%d%H}_f000_f240_06.nc'
 try:
  query='https://noaa-oar-mlwp-data.s3.amazonaws.com/?'+urllib.parse.urlencode({'list-type':'2','prefix':p,'max-keys':'1'});v=ET.fromstring(urllib.request.urlopen(query,timeout=25).read()).findtext('{*}KeyCount')
 except Exception as e:v='ERROR '+str(e)
 ofcl=r['ofcl_48']
 if name=='ISAIAS':
  u='https://ftp.nhc.noaa.gov/atcf/aid_public/aal092026.dat.gz'
  try:
   lines=gzip.decompress(urllib.request.urlopen(u,timeout=25).read()).decode().splitlines();ofcl='yes' if any(len(q:=list(map(str.strip,x.split(','))))>6 and q[2]==init.strftime('%Y%m%d%H') and q[4]=='OFCL' and q[5]=='48' for x in lines) else 'no'
  except Exception as e:ofcl='ERROR '+str(e)
 results.append(dict(event=name,init_utc=init.isoformat(),gfs_0p50_f048=status,gfs_idx_url=g,pangu_s3_keycount=v,pangu_key=p,ofcl_48=ofcl))
with (P/'input_availability.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,results[0].keys());w.writeheader();w.writerows(results)
print(*results,sep='\n')
