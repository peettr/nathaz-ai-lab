#!/usr/bin/env python3
"""Range-read 0-24h u10/v10 GraphCast archive; bilinear sample per station.
One complete initialization CSV per object, no global file downloaded.
"""
import argparse,json,time,traceback
from pathlib import Path
import numpy as np,pandas as pd,h5py,fsspec
ROOT=Path('/content/m4')
PERIODS={('OKC','train'):('2022-01-01','2023-01-01'),('OKC','test'):('2023-01-01','2024-01-01'),('Swiss','train'):('2023-10-01','2024-01-01'),('Swiss','test'):('2024-01-01','2024-04-01')}
def one(init,stations):
    url=f'https://noaa-oar-mlwp-data.s3.amazonaws.com/GRAP_v100_GFS/{init:%Y}/{init:%m%d}/GRAP_v100_GFS_{init:%Y%m%d%H}_f000_f240_06.nc'
    points=[]
    for s in stations:
        y=(90-s['lat'])*4;x=(s['lon']%360)*4;i=int(y);j=int(x);a=y-i;b=x-j
        points.append((s['station'],i,j,a,b))
    rows=[]
    with fsspec.open(url,'rb',block_size=262144,cache_type='readahead') as f:
      with h5py.File(f,'r') as h:
        if h['u10'].shape!=(41,721,1440) or h['v10'].shape!=(41,721,1440):raise ValueError('AIWP unexpected grid')
        if float(h['latitude'][0])!=90 or float(h['longitude'][1])!=.25:raise ValueError('AIWP grid orientation')
        for index in range(5):
          for site,i,j,a,b in points:
            uv=[]
            for key in ('u10','v10'):
              z=h[key][index,i:i+2,j:j+2]
              uv.append(float((1-a)*(1-b)*z[0,0]+a*(1-b)*z[1,0]+(1-a)*b*z[0,1]+a*b*z[1,1]))
            rows.append((site,init.isoformat(),index*6,*uv))
    return rows,url
def main():
    a=argparse.ArgumentParser();a.add_argument('net',choices=['OKC','Swiss']);a.add_argument('split',choices=['train','test']);x=a.parse_args()
    start,end=PERIODS[x.net,x.split]
    times=pd.date_range(pd.Timestamp(start,tz='UTC')-pd.Timedelta(hours=12),pd.Timestamp(end,tz='UTC'),freq='12h',inclusive='left')
    stations=json.loads((ROOT/f'{x.net}_stations.json').read_text())
    folder=ROOT/x.net/f'aiwp_{x.split}';folder.mkdir(parents=True,exist_ok=True)
    errors=ROOT/x.net/f'aiwp_{x.split}_errors.jsonl'
    for index,t in enumerate(times,1):
        init=t.to_pydatetime();p=folder/(init.strftime('%Y%m%d%H')+'.csv')
        if p.exists():continue
        try:
            rows,url=one(init,stations)
            if len(rows)!=5*len(stations):raise ValueError('incomplete AIWP initialization')
            q=p.with_suffix('.partial');pd.DataFrame(rows,columns=['site','init_utc','fhr','u','v']).to_csv(q,index=False);q.rename(p)
        except Exception:
            with errors.open('a') as f:f.write(json.dumps({'init':init.isoformat(),'error':traceback.format_exc()})+'\n')
        if index%10==0:print('AIWP',x.net,x.split,index,len(times),'complete',len(list(folder.glob('*.csv'))),flush=True)
    print('AIWP_DONE',x.net,x.split,len(list(folder.glob('*.csv'))),len(times),flush=True)
if __name__=='__main__':main()
