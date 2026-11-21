#!/usr/bin/env python3
"""Blind AIWP forecast-only retrieval. One immutable CSV/JSON per source/init; no scoring."""
import csv,datetime as dt,hashlib,json,os,time,traceback,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import numpy as np
import fsspec,h5py
ROOT=Path('/content/p1');SRC=('FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS');LEADS=(24,30,36,42,48)
def verify():
    frozen=ROOT/'stations_p2_frozen.csv';m=json.loads((ROOT/'freeze_manifest.json').read_text())
    assert hashlib.sha256(frozen.read_bytes()).hexdigest()==m['station_sha256']
    s=list(csv.DictReader(frozen.open()));assert len(s)==m['selected']
    return s

def work(src,t,stations):
    stamp=t.strftime('%Y%m%d%H');dest=ROOT/'forecast_parts'/f'{src}_{stamp}.csv';manifest=dest.with_suffix('.json')
    if dest.exists() and manifest.exists():return 'skip',src,stamp,0
    if dest.exists() or manifest.exists():return 'incomplete_existing',src,stamp,0
    url=f'https://noaa-oar-mlwp-data.s3.amazonaws.com/{src}/{t:%Y}/{t:%m%d}/{src}_{stamp}_f000_f240_06.nc'
    began=time.monotonic()
    try:
        with fsspec.open(url,'rb',block_size=262144).open() as stream:
            with h5py.File(stream,'r') as f:
                keys=['u10','v10']+(['u100','v100'] if src.startswith('FOUR') else [])
                assert all(k in f for k in keys),(src,list(f.keys()))
                coords=[((90-float(s['lat']))*4,(float(s['lon'])%360)*4) for s in stations]
                y0=max(0,int(min(y for y,x in coords))-2);y1=min(721,int(max(y for y,x in coords))+4)
                x0=max(0,int(min(x for y,x in coords))-2);x1=min(1440,int(max(x for y,x in coords))+4)
                rows=[]
                for lead in LEADS:
                    arrays={k:f[k][lead//6,y0:y1,x0:x1] for k in keys}
                    for s,(y,x) in zip(stations,coords):
                        yi=y-y0;xi=x-x0;i=int(yi);j=int(xi);a=yi-i;b=xi-j
                        def interp(k):
                            v=arrays[k];return float((1-a)*(1-b)*v[i,j]+a*(1-b)*v[i+1,j]+(1-a)*b*v[i,j+1]+a*b*v[i+1,j+1])
                        rows.append((s['station'],t.isoformat()+'Z',lead,src,interp('u10'),interp('v10'),interp('u100') if 'u100' in arrays else '',interp('v100') if 'v100' in arrays else '',url))
        with dest.open('x',newline='') as o:
            w=csv.writer(o);w.writerow(['station','init_utc','lead_h','source','fc_u10','fc_v10','fc_u100','fc_v100','object_url']);w.writerows(rows)
        assert len(rows)==len(stations)*len(LEADS)
        manifest.write_text(json.dumps({'source':src,'init':stamp,'rows':len(rows),'seconds':time.monotonic()-began,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'url':url}))
        return 'ok',src,stamp,round(time.monotonic()-began,2)
    except Exception as e:return 'error',src,stamp,traceback.format_exc()[-1500:]

def main():
    stations=verify();(ROOT/'forecast_parts').mkdir(exist_ok=True)
    allowed={(r['source'],r['init_utc'][:10].replace('-','')+r['init_utc'][11:13]) for line in (ROOT/'archive_availability.jsonl').open() if (r:=json.loads(line)).get('status')==200}
    todo=[]
    for a,b in [('2022-10-01','2023-04-01'),('2023-10-01','2024-04-01'),('2024-10-01','2025-04-01')]:
        t=dt.datetime.fromisoformat(a);end=dt.datetime.fromisoformat(b)
        while t<end:
            for src in SRC:
                if (src,t.strftime('%Y%m%d%H')) in allowed:todo.append((src,t))
            t+=dt.timedelta(hours=12)
    if os.environ.get('P1_PILOT')=='1':todo=todo[:3]
    progress=ROOT/'forecast_progress.jsonl'
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures=[pool.submit(work,src,t,stations) for src,t in todo]
        for n,f in enumerate(as_completed(futures),1):
            status,src,stamp,elapsed=f.result()
            with progress.open('a') as q:q.write(json.dumps({'status':status,'source':src,'init':stamp,'seconds_or_error':elapsed})+'\n')
            if n%10==0 or status=='error':print('FORECAST',n,len(todo),status,src,stamp,str(elapsed)[:300],flush=True)
    print('AI_STAGE_DONE',len(todo),flush=True)
if __name__=='__main__':main()
