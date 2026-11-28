#!/usr/bin/env python3
"""M6 GFS hourly multilayer extraction; run on Colab CPU only. One atomic CSV per init."""
import csv, json, math, os, sys, time, traceback, tarfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd
import requests
import eccodes
ROOT=Path('/content/m6'); ROOT.mkdir(exist_ok=True)
BASE='https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{day}/{hh}/atmos/gfs.t{hh}z.pgrb2.0p25.f{fhr:03d}'
LEVELS=(1000,975,950,925,900,850,800,750,700,650,600,550,500)
FIELDS=[('UGRD','10 m above ground'),('VGRD','10 m above ground'),('HGT','surface')]+[(v,f'{p} mb') for p in LEVELS for v in ('UGRD','VGRD','HGT')]
STATIONS=json.loads((ROOT/'stations.json').read_text()); assert len(STATIONS)==12

def get(url, headers=None):
    for n in range(4):
        try:
            r=requests.get(url,timeout=65,headers={'User-Agent':'R23.2-M6-research',**(headers or {})})
            if r.status_code in (200,206):return r
            if r.status_code not in (429,500,502,503,504):r.raise_for_status()
        except Exception:
            if n==3:raise
        time.sleep(2*(n+1))
    raise RuntimeError(url)

def sample(gid):
    ni=eccodes.codes_get(gid,'Ni');nj=eccodes.codes_get(gid,'Nj')
    if (ni,nj)!=(1440,721) or eccodes.codes_get(gid,'latitudeOfFirstGridPointInDegrees')!=90:raise ValueError('unexpected GFS grid')
    arr=eccodes.codes_get_array(gid,'values').reshape(nj,ni)
    out=[]
    for s in STATIONS:
        y=(90-s['lat'])*4;x=(s['lon']%360)*4;i=int(y);j=int(x);a=y-i;b=x-j
        out.append(float((1-a)*(1-b)*arr[i,j]+a*(1-b)*arr[i+1,j]+(1-a)*b*arr[i,j+1]+a*b*arr[i+1,j+1]))
    return out

def hour(init,fhr):
    url=BASE.format(day=init.strftime('%Y%m%d'),hh=init.strftime('%H'),fhr=fhr)
    idx=[line.split(':') for line in get(url+'.idx').text.splitlines()]
    found={(p[3],p[4]):i for i,p in enumerate(idx)}
    if not set(FIELDS)<=set(found):raise ValueError('missing fields '+str(set(FIELDS)-set(found)))
    def one(field):
        i=found[field];lo=int(idx[i][1]);hi=int(idx[i+1][1])-1
        r=get(url,{'Range':f'bytes={lo}-{hi}'})
        if r.status_code!=206 or len(r.content)!=hi-lo+1:raise ValueError('range mismatch '+repr(field))
        gid=eccodes.codes_new_from_message(r.content)
        try:return field,sample(gid)
        finally:eccodes.codes_release(gid)
    with ThreadPoolExecutor(max_workers=12) as pool:return dict(pool.map(one,FIELDS))

def features(data):
    rows=[]
    for i,s in enumerate(STATIONS):
        u=data['UGRD','10 m above ground'][i];v=data['VGRD','10 m above ground'][i]
        zsfc=data['HGT','surface'][i];zsite=s['z_site_asl'];layers=[]
        for p in LEVELS:
            h=data['HGT',f'{p} mb'][i];uu=data['UGRD',f'{p} mb'][i];vv=data['VGRD',f'{p} mb'][i]
            if np.isfinite(h) and np.isfinite(uu) and np.isfinite(vv) and h>=zsfc:layers.append((h,uu,vv))
        layers.sort()
        if zsite<=zsfc:eu,ev=u,v
        elif not layers:raise ValueError('no above-ground pressure layer '+s['site'])
        else:
            anchors=[(zsfc+10,u,v)]+[x for x in layers if x[0]>zsfc+10]
            if zsite<=anchors[0][0]:eu,ev=u,v
            elif zsite>=anchors[-1][0]:raise ValueError('site above 500 hPa '+s['site'])
            else:
                j=next(j for j in range(1,len(anchors)) if anchors[j][0]>=zsite)
                low,high=anchors[j-1],anchors[j];a=(zsite-low[0])/(high[0]-low[0]);eu=low[1]*(1-a)+high[1]*a;ev=low[2]*(1-a)+high[2]*a
        rows.append((s['site'],u,v,eu,ev,zsfc,zsite-zsfc))
    return rows

def run(stage):
    folder=ROOT/f'{stage}_gfs';folder.mkdir(exist_ok=True)
    dates=pd.date_range('2023-09-29T00:00Z','2023-12-31T18:00Z',freq='6h') if stage=='train' else pd.date_range('2023-12-31T00:00Z','2024-03-31T18:00Z',freq='6h')
    limit=int(os.environ.get('M6_LIMIT','0'))
    if limit:dates=dates[:limit]
    for seq,stamp in enumerate(dates,1):
        init=stamp.to_pydatetime();p=folder/f'{init:%Y%m%d%H}.csv'
        if p.exists():continue
        t=time.monotonic()
        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                fs={pool.submit(hour,init,h):h for h in range(19)}
                data={fs[f]:f.result() for f in as_completed(fs)}
            rows=[(site,init.isoformat(),h,u,v,eu,ev,z,dz) for h in range(19) for site,u,v,eu,ev,z,dz in features(data[h])]
            q=p.with_suffix('.partial')
            with q.open('w') as w:
                cw=csv.writer(w);cw.writerow(['site','init_utc','fhr','u','v','eu','ev','z_model_sfc','dz']);cw.writerows(rows)
            q.rename(p)
            with (ROOT/f'{stage}_progress.jsonl').open('a') as w:w.write(json.dumps({'init':init.isoformat(),'seq':seq,'total':len(dates),'seconds':round(time.monotonic()-t,2)})+'\n')
            if seq%5==0:print(stage.upper()+'_GFS',seq,len(dates),round(time.monotonic()-t,2),flush=True)
            if seq%25==0:
                tmp=ROOT/f'{stage}_checkpoint.partial';dest=ROOT/f'{stage}_checkpoint.tgz'
                with tarfile.open(tmp,'w:gz') as tar:tar.add(folder,arcname=folder.name)
                tmp.replace(dest)
                print(stage.upper()+'_CHECKPOINT',seq,dest.stat().st_size,flush=True)
        except Exception as e:
            with (ROOT/f'{stage}_errors.jsonl').open('a') as w:w.write(json.dumps({'init':init.isoformat(),'error':traceback.format_exc()})+'\n')
            print(stage.upper()+'_ERROR',init,repr(e),flush=True)
    if len(list(folder.glob('*.csv')))<len(dates):raise RuntimeError(f'incomplete {stage} GFS')
    print(stage.upper()+'_GFS_DONE',len(dates),flush=True)
if __name__=='__main__':run(sys.argv[1])
