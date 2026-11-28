"""Stream Paris monthly L3 archives, count QC-valid centered hours per station/gate."""
import io,tarfile,requests,h5py,numpy as np,pandas as pd,collections,json,time,os
from pathlib import Path
START=os.getenv('START','2022-06'); END=os.getenv('END','2024-03')
OUT=Path(__file__).with_name(f'paris_coverage_{START}_{END}.json')
URL='https://zenodo.org/api/records/17710093/files/paris_dwl_L3V1.42_{ym}_600s.tar.gz/content'
STATIONS=('PAARBO','PACHEM','PASIRT','PALUPD')
# Same hour mapping as paris_lidar_v2/run_observations.py. Preserve across archive boundaries.
raw=collections.defaultdict(dict); archive=[]
for period in pd.period_range(START,END,freq='M'):
    ym=str(period).replace('-','_');t0=time.time()
    r=requests.get(URL.format(ym=ym),timeout=180);r.raise_for_status();days=0
    with tarfile.open(fileobj=io.BytesIO(r.content),mode='r:gz') as tf:
        for m in tf:
            if not m.isfile() or not m.name.endswith('.nc'):continue
            days+=1
            with h5py.File(io.BytesIO(tf.extractfile(m).read()),'r') as f:
                stations=[x.decode() for x in f['station'][:]]
                alt=f['altitude'][:];ground=f['station_altitude'][:]-f['station_height'][:]
                times=pd.Timestamp(f['time'].attrs['units'].decode().split(' since ')[1],tz='UTC')+pd.to_timedelta(f['time'][:],unit='m')
                valid=(times-pd.Timedelta(minutes=5)).round('h')
                for s,name in enumerate(stations):
                    if name not in STATIONS:continue
                    for target in (50,100,150):
                        k=int(np.abs(alt-ground[s]-target).argmin());actual=float(alt[k]-ground[s])
                        if abs(actual-target)>12.5:continue
                        u=f['u'][s,:,k];v=f['v'][s,:,k]
                        for timestamp,hour,uu,vv in zip(times,valid,u,v):
                            if not (np.isfinite(uu) and np.isfinite(vv)):continue
                            if not pd.Timedelta(minutes=-20)<=timestamp-hour<=pd.Timedelta(minutes=30):continue
                            key=(str(hour.to_period('M')),name,target,round(actual,2),hour.isoformat())
                            raw[key][timestamp.isoformat()]=(float(uu),float(vv))
    archive.append({'month':str(period),'bytes':len(r.content),'daily_files':days,'seconds':round(time.time()-t0,1)})
    print('MONTH',str(period),'bytes',len(r.content),'days',days,'candidate_hour_bins',len(raw),'seconds',round(time.time()-t0,1),flush=True)
    # Persist monthly progress without raw observations.
    OUT.with_name('paris_fetch_progress.json').write_text(json.dumps(archive,indent=2))
rows=[]
for (month,station,target,actual,hour),items in raw.items():
    if len(items)<4:continue
    u=np.mean([v[0] for v in items.values()]);v=np.mean([v[1] for v in items.values()]);w=float(np.hypot(u,v))
    rows.append((month,station,target,actual,w,len(items)))
D=pd.DataFrame(rows,columns=['month','station','target','actual','wind','n10'])
summary=[]
for month in pd.period_range(START,END,freq='M'):
    for station in STATIONS:
        for target in (50,100,150):
            g=D[(D.month==str(month))&(D.station==station)&(D.target==target)]
            summary.append({'month':str(month),'station':station,'target_agl':target,'actual_agl':None if g.empty else float(g.actual.iloc[0]),'valid_hours':len(g),'mean_vector_speed':None if g.empty else round(float(g.wind.mean()),3),'median_vector_speed':None if g.empty else round(float(g.wind.median()),3),'n10_min':None if g.empty else int(g.n10.min())})
OUT.write_text(json.dumps({'method':'u/v finite L3v1.42, >=4 unique 10-min values within centered hour, vector mean then speed; duplicate daily overlap removed; UTC months', 'archives':archive,'monthly':summary},indent=2))
print('DONE',OUT,'bytes',sum(x['bytes'] for x in archive),'rows',len(rows),flush=True)
