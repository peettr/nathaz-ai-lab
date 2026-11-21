#!/usr/bin/env python3
"""Fetch 10-m U/V at station points: ARCO ERA5 and AWS HRRR f01, daily checkpoints."""
import json,re,sys,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import numpy as np,pandas as pd,requests,xarray as xr,eccodes as ec
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent
D=json.loads((R/'selected_dates.json').read_text()); st=pd.read_csv(R/'stations.csv')
st=st[['station','lat','lon']]
station_xyz=np.c_[np.cos(np.deg2rad(st.lat))*np.cos(np.deg2rad(st.lon)),np.cos(np.deg2rad(st.lat))*np.sin(np.deg2rad(st.lon)),np.sin(np.deg2rad(st.lat))]
ERA='gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
DS=xr.open_zarr(ERA,chunks=None,storage_options={'token':'anon'})[['10m_u_component_of_wind','10m_v_component_of_wind']]
# scipy interpolation via xarray, coordinates expressed 0..360
loc={'latitude':xr.DataArray(st.lat.to_numpy(),dims='station'),'longitude':xr.DataArray((st.lon.to_numpy()%360),dims='station')}
def era_day(date):
 a=DS.sel(time=slice(date,date+'T23:00:00')).interp(**loc).load()
 assert len(a.time)==24
 rows=[]
 for i,t in enumerate(pd.to_datetime(a.time.values,utc=True)):
  for j,s in enumerate(st.station):rows.append((s,t.isoformat(),float(a['10m_u_component_of_wind'].values[i,j]),float(a['10m_v_component_of_wind'].values[i,j])))
 return pd.DataFrame(rows,columns=['station','hour','era_u','era_v'])
def hrrr_hour(t):
 # f01 initialized 1 hour before valid time. Each thread owns session.
 init=t-pd.Timedelta(hours=1)
 url=f'https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.{init:%Y%m%d}/conus/hrrr.t{init:%H}z.wrfsfcf01.grib2'
 session=requests.Session();session.headers['User-Agent']='NatHaz-AI-Lab-obs-fusion/1.0'
 for attempt in range(3):
  try:
   r=session.get(url+'.idx',timeout=60);r.raise_for_status();lines=r.text.splitlines()
   found={}
   for i,line in enumerate(lines):
    m=re.search(r':(UGRD|VGRD):10 m above ground:1 hour fcst:',line)
    if m:
     start=int(line.split(':')[1]);end=int(lines[i+1].split(':')[1])-1 if i+1<len(lines) else None
     found[m.group(1)]=(start,end)
   if len(found)!=2:raise RuntimeError('missing 10m U/V in '+url)
   result={}
   for key,(start,end) in found.items():
    rr=session.get(url,headers={'Range':f'bytes={start}-{end}'},timeout=90);rr.raise_for_status()
    if rr.status_code!=206:raise RuntimeError('range request did not return 206')
    h=ec.codes_new_from_message(rr.content)
    try:
     vals=ec.codes_get_array(h,'values')
     if key=='UGRD':
      lat=ec.codes_get_array(h,'latitudes');lon=ec.codes_get_array(h,'longitudes');index=cKDTree(np.c_[np.cos(np.deg2rad(lat))*np.cos(np.deg2rad(lon)),np.cos(np.deg2rad(lat))*np.sin(np.deg2rad(lon)),np.sin(np.deg2rad(lat))]).query(station_xyz)[1]
     result[key]=vals
    finally:ec.codes_release(h)
   return pd.DataFrame({'station':st.station,'hour':t.isoformat(),'hrrr_u':result['UGRD'][index],'hrrr_v':result['VGRD'][index]})
  except Exception as e:
   if attempt==2:raise RuntimeError(f'{url}: {e}') from e
   time.sleep(2*(attempt+1))
for date in D:
 efile=R/f'era_{date}.csv';hfile=R/f'hrrr_{date}.csv'
 if not efile.exists():
  era_day(date).to_csv(efile,index=False);print('ERA',date,flush=True)
 if not hfile.exists():
  hours=pd.date_range(date,periods=24,freq='h',tz='UTC')
  rows=[]
  with ThreadPoolExecutor(max_workers=4) as pool:
   futures={pool.submit(hrrr_hour,t):t for t in hours}
   for future in as_completed(futures):
    rows.append(future.result());print('HRRR',date,str(futures[future]),flush=True)
  pd.concat(rows,ignore_index=True).sort_values(['hour','station']).to_csv(hfile,index=False)
print('BACKGROUNDS_COMPLETE')
