#!/usr/bin/env python3
"""Paris side-arm GFS station-only range fetch, Colab CPU; resumable per init.
GFS 0.25-degree 10/100m U/V at fhr 6,12,24,48, interpolated
component-wise to the target ten-minute interval midpoint (fhr-5 min).
"""
import csv, json, math, os, sys, time, traceback, tarfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd
import requests
import eccodes

ROOT=Path('/content/m5'); OUT=ROOT/'paris_gfs'; OUT.mkdir(exist_ok=True)
BASE='https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{day}/{hh}/atmos/gfs.t{hh}z.pgrb2.0p25.f{fhr:03d}'
# A1 v2 archived PALUPD coordinate (run_forecasts.py); site location is not learned from test data.
LAT,LON=48.85,2.35
FHRS=(6,12,24,48); PREV={6:5,12:11,24:23,48:45}
FIELDS=[(v,z) for z in ('10 m above ground','100 m above ground') for v in ('UGRD','VGRD')]

def get(url,headers=None):
    for n in range(4):
        try:
            r=requests.get(url,headers={'User-Agent':'R23.2-M5-Paris',**(headers or {})},timeout=70)
            if r.status_code in (200,206): return r
            if r.status_code not in (429,500,502,503,504):r.raise_for_status()
        except Exception:
            if n==3:raise
        time.sleep((n+1)*2)
    raise RuntimeError('request exhausted '+url)

def sample(gid):
    if (eccodes.codes_get(gid,'Ni'),eccodes.codes_get(gid,'Nj'))!=(1440,721):raise ValueError('GFS grid')
    if eccodes.codes_get(gid,'latitudeOfFirstGridPointInDegrees')!=90:raise ValueError('GFS orientation')
    vals=eccodes.codes_get_array(gid,'values').reshape(721,1440)
    y=(90-LAT)*4;x=LON*4;i=int(y);j=int(x);a=y-i;b=x-j
    return float((1-a)*(1-b)*vals[i,j]+a*(1-b)*vals[i+1,j]+(1-a)*b*vals[i,j+1]+a*b*vals[i+1,j+1])

def hour(init,fhr):
    url=BASE.format(day=init.strftime('%Y%m%d'),hh=init.strftime('%H'),fhr=fhr)
    idx=[line.split(':') for line in get(url+'.idx').text.splitlines()]
    found={(p[3],p[4]):i for i,p in enumerate(idx)}
    if not set(FIELDS)<=set(found):raise ValueError('missing '+str(set(FIELDS)-set(found)))
    def one(field):
        i=found[field];lo=int(idx[i][1]);hi=int(idx[i+1][1])-1
        response=get(url,headers={'Range':f'bytes={lo}-{hi}'})
        if response.status_code!=206 or len(response.content)!=hi-lo+1:raise ValueError('range mismatch '+str(field))
        gid=eccodes.codes_new_from_message(response.content)
        try:return field,sample(gid)
        finally:eccodes.codes_release(gid)
    with ThreadPoolExecutor(max_workers=4) as pool:return dict(pool.map(one,FIELDS))

def stage():
    # The earliest pre-interval cycle is included so training observations never borrow a test-period fit.
    dates=pd.date_range('2023-05-30T00:00Z','2024-02-29T18:00Z',freq='6h')
    lim=int(os.environ.get('M5_PARIS_LIMIT','0'))
    if lim:dates=dates[:lim]
    fail=[]
    for seq,stamp in enumerate(dates,1):
        init=stamp.to_pydatetime();p=OUT/f'{init:%Y%m%d%H}.csv'
        if p.exists():continue
        t=time.monotonic()
        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures={pool.submit(hour,init,f):f for f in sorted(set(PREV.values())|set(FHRS))}
                data={futures[j]:j.result() for j in as_completed(futures)}
            rows=[]
            for fhr in FHRS:
                alpha=(fhr-1/12-PREV[fhr])/(fhr-PREV[fhr]); v={field:(1-alpha)*data[PREV[fhr]][field]+alpha*data[fhr][field] for field in FIELDS}
                rows.append([init.isoformat(),fhr,*(v['UGRD',z] for z in ('10 m above ground','100 m above ground')),
                             *(v['VGRD',z] for z in ('10 m above ground','100 m above ground'))])
            part=p.with_suffix('.partial')
            with part.open('w') as w:
                wr=csv.writer(w);wr.writerow(['init_utc','fhr','u10','u100','v10','v100']);wr.writerows(rows)
            os.replace(part,p)
            with (ROOT/'paris_gfs_progress.jsonl').open('a') as w:w.write(json.dumps({'init':init.isoformat(),'done':seq,'total':len(dates),'seconds':round(time.monotonic()-t,2)})+'\n')
            if seq%10==0:print('PARIS_GFS',seq,len(dates),round(time.monotonic()-t,1),flush=True)
            if seq%100==0:
                archive=ROOT/f'paris_gfs_checkpoint_{seq:04d}.tgz'
                if not archive.exists():
                    with tarfile.open(archive,'w:gz') as tf:
                        for item in sorted(OUT.glob('*.csv')):tf.add(item,arcname='paris_gfs/'+item.name)
                    print('PARIS_CHECKPOINT',archive.name,archive.stat().st_size,flush=True)
        except Exception as ex:
            fail.append((str(init),repr(ex)))
            with (ROOT/'paris_gfs_errors.jsonl').open('a') as w:w.write(json.dumps({'init':init.isoformat(),'trace':traceback.format_exc()})+'\n')
            print('PARIS_ERROR',seq,repr(ex),flush=True)
    existing=len(list(OUT.glob('*.csv')))
    print('PARIS_GFS_DONE',existing,len(dates),'failed',len(fail),flush=True)
    if existing!=len(dates):raise RuntimeError('incomplete GFS; recover only missing in same session')
if __name__=='__main__':stage()
