"""Extract Paris L3 V1.42 600s QC-cleared u/v at nearest AGL gates; emit centered-hour vector means."""
import io,tarfile,requests,h5py,numpy as np,pandas as pd,time,json
from pathlib import Path
O=Path('/content/paris_a1');O.mkdir(exist_ok=True)
url='https://zenodo.org/api/records/17710093/files/paris_dwl_L3V1.42_{ym}_600s.tar.gz/content'
months=pd.period_range('2022-06','2024-03',freq='M')
for period in months:
 ym=str(period).replace('-','_');out=O/f'obs_{ym}.csv';
 if out.exists():continue
 t0=time.time();r=requests.get(url.format(ym=ym),timeout=180);r.raise_for_status();rows=[]
 with tarfile.open(fileobj=io.BytesIO(r.content),mode='r:gz') as tf:
  for member in tf:
   if not member.isfile() or not member.name.endswith('.nc'):continue
   with h5py.File(io.BytesIO(tf.extractfile(member).read()),'r') as f:
    stations=[s.decode() for s in f['station'][:]];alt=f['altitude'][:];ground=f['station_altitude'][:]-f['station_height'][:]
    times=pd.Timestamp(f['time'].attrs['units'].decode().split(' since ')[1],tz='UTC')+pd.to_timedelta(f['time'][:],unit='m')
    for s,name in enumerate(stations):
     for z in (50,100,150):
      k=int(np.abs(alt-ground[s]-z).argmin());real=float(alt[k]-ground[s]);
      if abs(real-z)>12.5:continue
      uu=f['u'][s,:,k];vv=f['v'][s,:,k]
      for ts,u,v in zip(times,uu,vv):
       if np.isfinite(u) and np.isfinite(v):rows.append((name,z,real,float(f['station_lat'][s]),float(f['station_lon'][s]),ts.isoformat(),float(u),float(v)))
 raw=pd.DataFrame(rows,columns=['station','target_agl','actual_agl','lat','lon','end_utc','u','v'])
 if len(raw):
  raw['end_utc']=pd.to_datetime(raw.end_utc,utc=True)
  # Each L3 10-minute time is END of interval. Six windows ending at t-20,-10,0,+10,+20,+30 cover [t-30,t+30].
  raw['valid_utc']=(raw.end_utc-pd.Timedelta(minutes=5)).dt.round('h')
  raw=raw[(raw.end_utc-raw.valid_utc>=pd.Timedelta(minutes=-20)) & (raw.end_utc-raw.valid_utc<=pd.Timedelta(minutes=30))]
  g=raw.groupby(['station','target_agl','actual_agl','lat','lon','valid_utc'],as_index=False).agg(u=('u','mean'),v=('v','mean'),n10=('u','size'))
  g=g[g.n10>=4].copy();g['wind']=np.hypot(g.u,g.v)
 else:g=pd.DataFrame(columns=['station','target_agl','actual_agl','lat','lon','valid_utc','u','v','n10','wind'])
 g.to_csv(out,index=False)
 print('OBS',ym,'bytes',len(r.content),'rows',len(g),'stations',g.groupby(['station','target_agl']).size().to_dict(),'sec',round(time.time()-t0),flush=True)
(O/'obs_done.json').write_text(json.dumps({'months':len(months),'utc':pd.Timestamp.now(tz='UTC').isoformat()}))
print('OBS_DONE',flush=True)
