#!/usr/bin/env python3
"""Bounded metadata/range audit; never downloads a GRIB body."""
import concurrent.futures, datetime, json, re, urllib.request, urllib.error
from pathlib import Path
R=Path(__file__).resolve().parent
TS='https://thredds.rda.ucar.edu/thredds/dodsC/files/g/d084003/2020/'
OS='https://osdf-director.osg-htc.org/ncar/gdex/d084003/2020/'
times=['2020060600','2020060606','2020060700','2020060706','2020060800','2020060806']
extra=['2020060500','2020060506']
def get(url, timeout=20):
 req=urllib.request.Request(url,headers={'Range':'bytes=0-15' if '.grib2' in url and not any(url.endswith(s) for s in ('.dds','.ascii','.html')) else 'bytes=0-300000','User-Agent':'Mozilla/5.0'})
 try:
  with urllib.request.urlopen(req,timeout=timeout) as res:
   body=res.read(300000 if not url.endswith('.grib2') else 16)
   return {'url':url,'status':res.status,'content_range':res.headers.get('Content-Range'),'bytes_read':len(body),'body':body.decode(errors='replace') if not url.endswith('.grib2') else body.hex()}
 except urllib.error.HTTPError as exc: return {'url':url,'status':exc.code,'error':str(exc)}
 except Exception as exc: return {'url':url,'status':None,'error':repr(exc)}
def one(t):
 d=t[:8]; name=f'gfs.0p25b.{t}.f000.grib2'; base=f'{TS}{d}/{name}'; obj=get(f'{OS}{d}/{name}'); dds=get(base+'.dds'); item={'time':t,'object':obj,'dds_status':dds['status'],'dds_url':dds['url']}
 if dds['status']==200:
  s=dds['body']; item['dimensions']={k:int(v) for k,v in re.findall(r'Float32 (isobaric\d*)\[isobaric\d* = (\d+)\]',s)}
  item['field_dimensions']={k:re.search(re.escape(k)+r'\[time = 1\]\[(isobaric\d*) = (\d+)\]',s).groups() if re.search(re.escape(k)+r'\[time = 1\]\[(isobaric\d*) = (\d+)\]',s) else None for k in ['Geopotential_height_isobaric','Temperature_isobaric','u-component_of_wind_isobaric','v-component_of_wind_isobaric','Relative_humidity_isobaric','Specific_humidity_isobaric','Vertical_velocity_pressure_isobaric']}
  coords={}
  for key in ('isobaric1','isobaric2','isobaric3'):
   c=get(base+'.ascii?'+key); coords[key]={'url':c['url'],'status':c['status']}
   if c['status']==200:
    tail=c['body'].split('---------------------------------------------')[-1]; coords[key]['levels_pa']=[float(x) for x in re.findall(r'(?<![\w])\d+\.\d+(?![\w])',tail)]
  item['coordinates']=coords
 return item
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: rows=list(pool.map(one,times))
other=[]
for host in ['https://noaa-gfs-bdp-pds.s3.amazonaws.com','https://storage.googleapis.com/global-forecast-system']:
 t='2020060806';other.append(get(f'{host}/gfs.{t[:8]}/{t[8:]}/atmos/gfs.t{t[8:]}z.pgrb2b.0p25.f000'))
other.append(get('https://www.ncei.noaa.gov/data/global-forecast-system/access/grid-004-0.5-degree/analysis/202006/20200608/gfs_4_20200608_0600_000.grb2'))
out={'checked_at_est':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).isoformat(),'scope':'Metadata and 16-byte Range only; no large downloads','rows':rows,'additional_candidates':other}
p=R/'PGRB2B_ARCHIVE_PROBE_20261112.json'; p.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n'); print(p)
for row in rows: print(row['time'],row['object']['status'],row['dds_status'],row.get('field_dimensions'),{k:(v['status'],v.get('levels_pa')) for k,v in row.get('coordinates',{}).items() if k in ('isobaric1','isobaric2')})
for row in other: print(row['status'],row['url'])
