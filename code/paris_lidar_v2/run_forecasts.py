"""Concurrent resumable AIWP HDF5 remote slices and GFS GRIB2 .idx ranges; station-only CSV.
Run on Colab: python run_forecasts.py --workers 24 --start 2023-06-01 --end 2024-03-05
"""
import argparse, concurrent.futures, json, os, time, traceback
from pathlib import Path
import numpy as np, pandas as pd, requests, fsspec, h5py
SOURCES=('FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS','GFS')
AIURL='https://noaa-oar-mlwp-data.s3.amazonaws.com/{source}/{year}/{mmdd}/{source}_{date}_f000_f240_06.nc'
GFSURL='https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{ymd}/{hh}/atmos/gfs.t{hh}z.pgrb2.0p25.f{lead:03d}'
# Global regular lat-lon 0.25-degree mesh, 90N/0E origin; city window surrounds Paris.
I0,I1,J0,J1=155,175,0,25
STATIONS={'PALUPD':(48.85,2.35)}
def bilinear(field,lat,lon):
 yi=(90-lat)*4-I0;xi=(lon%360)*4-J0;i=int(np.floor(yi));j=int(np.floor(xi));a=yi-i;b=xi-j
 if not (0<=i<field.shape[0]-1 and 0<=j<field.shape[1]-1):raise ValueError((lat,lon,field.shape))
 q=field[i:i+2,j:j+2]
 return float((1-a)*(1-b)*q[0,0]+a*(1-b)*q[1,0]+(1-a)*b*q[0,1]+a*b*q[1,1])
def ai(source,init,stations):
 url=AIURL.format(source=source,year=init.year,mmdd=init.strftime('%m%d'),date=init.strftime('%Y%m%d%H'))
 h=fsspec.open(url,'rb',block_size=262144).open()
 try:
  with h5py.File(h,'r') as f:
   names=['u10','v10']+(['u100','v100'] if source.startswith('FOUR') else [])
   for n in names:
    if n not in f:raise KeyError(f'{n} absent {url}')
   rows=[]
   for lead in (24,48):
    fields={n:f[n][lead//6,I0:I1,J0:J1] for n in names}
    for station,lat,lon in stations:
     vals={n:bilinear(fields[n],lat,lon) for n in names}
     rows.append([station,init.isoformat(),lead,source,vals['u10'],vals['v10'],vals.get('u100',np.nan),vals.get('v100',np.nan)])
  return rows,url,getattr(h,'details',{}).get('size')
 finally:h.close()
def req(url,headers=None):
 for i in range(3):
  try:
   r=requests.get(url,headers=headers,timeout=75)
   if r.status_code in (200,206):return r
   if r.status_code not in (429,500,502,503,504):raise RuntimeError(f'{r.status_code} {url}')
  except requests.RequestException:
   if i==2:raise
  time.sleep(2*(i+1))
 raise RuntimeError(url)
def gfs(init,stations):
 import eccodes
 rows=[];total=0
 for lead in (24,48):
  url=GFSURL.format(ymd=init.strftime('%Y%m%d'),hh=init.strftime('%H'),lead=lead)
  r=req(url+'.idx');total+=len(r.content);idx=[l.split(':') for l in r.text.splitlines()];fields={}
  for key in ('UGRD','VGRD'):
   for height in ('10 m above ground','100 m above ground'):
    p=next(i for i,x in enumerate(idx) if x[3]==key and x[4]==height)
    a=int(idx[p][1]);b=int(idx[p+1][1])-1
    response=req(url,{'Range':f'bytes={a}-{b}'})
    if response.status_code!=206 or len(response.content)!=b-a+1:raise ValueError('range unsupported')
    total+=len(response.content)
    gid=eccodes.codes_new_from_message(response.content)
    try:
     if (eccodes.codes_get(gid,'Ni'),eccodes.codes_get(gid,'Nj'))!=(1440,721):raise ValueError('grid')
     if (eccodes.codes_get(gid,'latitudeOfFirstGridPointInDegrees'),eccodes.codes_get(gid,'longitudeOfFirstGridPointInDegrees'))!=(90,0):raise ValueError('orientation')
     field=eccodes.codes_get_array(gid,'values').reshape(721,1440)[I0:I1,J0:J1]
     fields[key,height]=[bilinear(field,lat,lon) for _,lat,lon in stations]
    finally:eccodes.codes_release(gid)
  for j,(station,lat,lon) in enumerate(stations):
   rows.append([station,init.isoformat(),lead,'GFS',fields['UGRD','10 m above ground'][j],fields['VGRD','10 m above ground'][j],fields['UGRD','100 m above ground'][j],fields['VGRD','100 m above ground'][j]])
 return rows,url,total
def task(source,init,stations,root):
 folder=root/'parts'/source;folder.mkdir(parents=True,exist_ok=True);stem=f'{source}_{init:%Y%m%d%H}';csv=folder/(stem+'.csv');meta=folder/(stem+'.json');err=folder/(stem+'.error')
 if csv.exists() and meta.exists():return ('SKIP',stem,0)
 if csv.exists() or meta.exists():return ('PARTIAL',stem,0)
 t=time.monotonic()
 try:
  rows,url,nbytes=gfs(init,stations) if source=='GFS' else ai(source,init,stations)
  if len(rows)!=2*len(stations):raise ValueError('incomplete')
  df=pd.DataFrame(rows,columns=['station','init_utc','lead_h','source','fc_u','fc_v','fc_u100','fc_v100'])
  tmp=csv.with_suffix('.part');df.to_csv(tmp,index=False);os.replace(tmp,csv)
  detail={'source':source,'init':init.isoformat(),'url':url,'source_object_bytes_or_ranges':nbytes,'station_rows':len(rows),'seconds':round(time.monotonic()-t,2)}
  tmp=meta.with_suffix('.part');tmp.write_text(json.dumps(detail));os.replace(tmp,meta)
  return ('OK',stem,detail['seconds'])
 except Exception:
  err.write_text(traceback.format_exc());return ('ERROR',stem,round(time.monotonic()-t,2))
def main():
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=20);p.add_argument('--start',default='2023-06-01');p.add_argument('--end',default='2024-03-05');p.add_argument('--out',default='/content/paris_a1_v2');p.add_argument('--stations',default='/content/paris_a1_v2/stations.csv');a=p.parse_args()
 stations=pd.read_csv(a.stations)[['station','lat','lon']].itertuples(index=False,name=None);stations=list(stations)
 root=Path(a.out);root.mkdir(parents=True,exist_ok=True)
 inits=pd.date_range(a.start,a.end,freq='12h',tz='UTC',inclusive='left')
 tasks=[(s,d) for d in inits for s in SOURCES];counts={};t0=time.monotonic()
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
  jobs={pool.submit(task,s,d,stations,root):(s,d) for s,d in tasks}
  for n,fut in enumerate(concurrent.futures.as_completed(jobs),1):
   status,stem,sec=fut.result();counts[status]=counts.get(status,0)+1
   if n%20==0 or status not in ('OK','SKIP'):
    print('PROGRESS',n,len(tasks),counts,stem,'sec',round(time.monotonic()-t0),flush=True)
   if n%20==0 or n==len(tasks):
    tmp=root/'forecast_progress.part';tmp.write_text(json.dumps({'done':n,'total':len(tasks),'counts':counts,'seconds':round(time.monotonic()-t0),'last':stem}));os.replace(tmp,root/'forecast_progress.json')
 print('FORECAST_DONE',counts,flush=True)
if __name__=='__main__':main()
