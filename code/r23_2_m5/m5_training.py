#!/usr/bin/env python3
"""Training-only GFS multilayer extraction for preregistered Swiss M5.
Per-initialization checkpoints; no test observations are opened by this program.
"""
import csv, io, json, math, os, sys, time, traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd
import requests
import eccodes

ROOT = Path('/content/m5')
ROOT.mkdir(exist_ok=True)
BASE = 'https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{day}/{hh}/atmos/gfs.t{hh}z.pgrb2.0p25.f{fhr:03d}'
LEVELS = (1000,975,950,925,900,850,800,750,700,650,600,550,500)
FHRS = (6,12,24,48)
# f048 has three-hourly output. The midpoint preceding f048 lies between f045 and f048.
PREV = {6:5,12:11,24:23,48:45}
FIELDS = [('UGRD','10 m above ground'),('VGRD','10 m above ground'),('HGT','surface')]+[(v,f'{p} mb') for p in LEVELS for v in ('UGRD','VGRD','HGT')]
STATIONS = json.loads((ROOT/'stations.json').read_text())
assert len(STATIONS)==12
SESSION=requests.Session()

def get(url,**kw):
    for n in range(4):
        try:
            r=requests.get(url, timeout=65, headers={'User-Agent':'R23.2-M5-research',**kw.pop('headers',{})},**kw)
            if r.status_code in (200,206): return r
            if r.status_code not in (429,500,502,503,504):r.raise_for_status()
        except Exception:
            if n==3:raise
        time.sleep(2*(n+1))
    raise RuntimeError(url)

def sample(gid):
    ni=eccodes.codes_get(gid,'Ni'); nj=eccodes.codes_get(gid,'Nj')
    if (ni,nj)!=(1440,721) or eccodes.codes_get(gid,'latitudeOfFirstGridPointInDegrees')!=90:
        raise ValueError('unexpected GFS grid')
    arr=eccodes.codes_get_array(gid,'values').reshape(nj,ni)
    out=[]
    for s in STATIONS:
        y=(90-s['lat'])*4; x=(s['lon']%360)*4; i=int(y);j=int(x);a=y-i;b=x-j
        out.append(float((1-a)*(1-b)*arr[i,j]+a*(1-b)*arr[i+1,j]+(1-a)*b*arr[i,j+1]+a*b*arr[i+1,j+1]))
    return out

def hour(init,fhr):
    url=BASE.format(day=init.strftime('%Y%m%d'),hh=init.strftime('%H'),fhr=fhr)
    idx=[line.split(':') for line in get(url+'.idx').text.splitlines()]
    found={(p[3],p[4]):i for i,p in enumerate(idx)}
    if not set(FIELDS)<=set(found):raise ValueError('missing fields '+str(set(FIELDS)-set(found)))
    def one(field):
        i=found[field];lo=int(idx[i][1]);hi=int(idx[i+1][1])-1
        r=get(url,headers={'Range':f'bytes={lo}-{hi}'})
        if r.status_code!=206 or len(r.content)!=hi-lo+1:raise ValueError('range mismatch '+repr(field))
        gid=eccodes.codes_new_from_message(r.content)
        try:return field,sample(gid)
        finally:eccodes.codes_release(gid)
    with ThreadPoolExecutor(max_workers=12) as pool:
        out=dict(pool.map(one,FIELDS))
    return out

def features(d0,d1,alpha):
    fields={key:np.array(d0[key])*(1-alpha)+np.array(d1[key])*alpha for key in FIELDS}
    rows=[]
    for i,s in enumerate(STATIONS):
        raw=math.hypot(fields['UGRD','10 m above ground'][i],fields['VGRD','10 m above ground'][i])
        zsurf=fields['HGT','surface'][i]
        zs=s['z_site_asl']
        layers=[]
        for p in LEVELS:
            h=fields['HGT',f'{p} mb'][i]
            u=fields['UGRD',f'{p} mb'][i]
            v=fields['VGRD',f'{p} mb'][i]
            if np.isfinite(h) and np.isfinite(u) and np.isfinite(v) and h>=zsurf:
                layers.append((h,u,v))
        layers.sort()
        if zs<=zsurf:eu,ev=fields['UGRD','10 m above ground'][i],fields['VGRD','10 m above ground'][i]
        elif not layers: raise ValueError('no above-ground pressure layer '+s['site'])
        else:
            anchors=[(zsurf+10,fields['UGRD','10 m above ground'][i],fields['VGRD','10 m above ground'][i])]+[x for x in layers if x[0]>zsurf+10]
            if zs<=anchors[0][0]:eu,ev=anchors[0][1:]
            elif zs>=anchors[-1][0]:raise ValueError('site above 500 hPa '+s['site'])
            else:
                j=next(j for j in range(1,len(anchors)) if anchors[j][0]>=zs)
                low,high=anchors[j-1],anchors[j]
                a=(zs-low[0])/(high[0]-low[0]);eu=low[1]*(1-a)+high[1]*a;ev=low[2]*(1-a)+high[2]*a
        rows.append((s['site'],raw,math.hypot(eu,ev),zsurf,zs-zsurf))
    return rows

def stage():
    folder=ROOT/'train_gfs';folder.mkdir(exist_ok=True)
    dates=pd.date_range('2023-09-29T00:00:00Z','2023-12-31T18:00:00Z',freq='6h')
    limit=int(os.environ.get('M5_LIMIT','0'))
    if limit:dates=dates[:limit]
    for seq,stamp in enumerate(dates,1):
        init=stamp.to_pydatetime();p=folder/f'{init:%Y%m%d%H}.csv'
        if p.exists():continue
        t=time.monotonic()
        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                fs={pool.submit(hour,init,h):h for h in sorted(set(PREV.values())|set(FHRS))}
                data={fs[f]:f.result() for f in as_completed(fs)}
            rows=[]
            for fhr in FHRS:
                mid=fhr-1/12;alpha=(mid-PREV[fhr])/(fhr-PREV[fhr])
                for site,raw,v1,zs,dz in features(data[PREV[fhr]],data[fhr],alpha):
                    rows.append((site,init.isoformat(),fhr,raw,v1,zs,dz))
            q=p.with_suffix('.partial')
            with q.open('w') as w:
                cw=csv.writer(w);cw.writerow(['site','init_utc','fhr','raw','v1','z_model_sfc','dz']);cw.writerows(rows)
            q.rename(p)
            with (ROOT/'progress.jsonl').open('a') as w:w.write(json.dumps({'init':init.isoformat(),'done':seq,'total':len(dates),'seconds':round(time.monotonic()-t,2)})+'\n')
            if seq%5==0:print('TRAIN_GFS',seq,len(dates),round(time.monotonic()-t,2),flush=True)
        except Exception as e:
            with (ROOT/'errors.jsonl').open('a') as w:w.write(json.dumps({'init':init.isoformat(),'error':traceback.format_exc()})+'\n')
            print('TRAIN_ERROR',init,repr(e),flush=True)
    if len(list(folder.glob('*.csv')))<len(dates):raise RuntimeError('incomplete train GFS')
    print('TRAIN_GFS_DONE',len(dates),flush=True)

def fit():
    paths=sorted((ROOT/'train_gfs').glob('*.csv'))
    if len(paths)!=len(pd.date_range('2023-09-29T00:00Z','2023-12-31T18:00Z',freq='6h')):raise ValueError('incomplete training GFS')
    fc=pd.concat(map(pd.read_csv,paths),ignore_index=True)
    fc['init_utc']=pd.to_datetime(fc.init_utc,utc=True)
    fc['valid_end_utc']=fc.init_utc+pd.to_timedelta(fc.fhr,unit='h')
    fc=fc[(fc.valid_end_utc>=pd.Timestamp('2023-10-01',tz='UTC'))&(fc.valid_end_utc<pd.Timestamp('2024-01-01',tz='UTC'))]
    obs=pd.concat([pd.read_csv(p,usecols=['station','time_utc','speed_ms']) for p in sorted((ROOT/'obs').glob('obs_*.csv'))],ignore_index=True)
    obs=obs.rename(columns={'station':'site','time_utc':'valid_end_utc','speed_ms':'obs'})
    obs.valid_end_utc=pd.to_datetime(obs.valid_end_utc,utc=True)
    obs=obs[(obs.valid_end_utc>=pd.Timestamp('2023-10-01',tz='UTC'))&(obs.valid_end_utc<pd.Timestamp('2024-01-01',tz='UTC'))]
    train=fc.merge(obs,on=['site','valid_end_utc'],how='inner').dropna(subset=['obs','raw','v1','dz'])
    train['terrain']=train.site.map({s['site']:s['terrain'] for s in STATIONS})
    if len(train)<10000:raise ValueError('too few pairs '+str(len(train)))
    train.to_parquet(ROOT/'train_pairs.parquet',index=False)
    # D1 LOSO fits. All held-out-site observation rows are excluded from the coefficient fit.
    coefs={}
    for site in sorted(train.site.unique()):
        for fhr in FHRS:
            sub=train[(train.site!=site)&(train.fhr==fhr)]
            x=np.column_stack([np.ones(len(sub)),sub.v1.to_numpy()]);y=sub.obs.to_numpy()
            if len(sub)<200:raise ValueError('D1 low sample '+site+' '+str(fhr))
            c=np.linalg.lstsq(x,y,rcond=None)[0]
            coefs[f'{site}:{fhr}']={'a':float(c[0]),'b':float(c[1]),'n':len(sub)}
    (ROOT/'d1_coefficients.json').write_text(json.dumps(coefs,indent=2))
    print('D1_FIT_DONE',len(train),len(coefs),flush=True)

if __name__=='__main__':
    step=sys.argv[1]
    {'gfs':stage,'fit':fit}[step]()
