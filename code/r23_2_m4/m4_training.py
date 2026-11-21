#!/usr/bin/env python3
"""M4 OKC training-only acquisition & linear MOS; no holdout is read.
S3 .idx HTTP ranges for GFS f000..f018 10m U/V; restart skips complete init CSVs.
"""
import argparse,csv,io,json,math,os,time,traceback
from pathlib import Path
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
import numpy as np,pandas as pd,requests,eccodes
KNOT=.5144444444444445
ROOT=Path('/content/m4');ROOT.mkdir(exist_ok=True)
STATIONS=['GOK','OKC','PWA']
URL='https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{ymd}/{hh}/atmos/gfs.t{hh}z.pgrb2.0p25.f{lead:03d}'
OBS='https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py'
def get(url,**kw):
    headers={'User-Agent':'M4-weather-research',**kw.pop('headers',{})}
    for n in range(4):
        try:
            r=requests.get(url,timeout=60,headers=headers,**kw)
            if r.status_code in (200,206):return r
            if r.status_code not in (429,500,502,503,504):r.raise_for_status()
        except Exception:
            if n==3:raise
        time.sleep(2*(n+1))
    raise RuntimeError('failed HTTP '+url)
def sample(gid,stations):
    ni=eccodes.codes_get(gid,'Ni');nj=eccodes.codes_get(gid,'Nj')
    if (ni,nj)!=(1440,721) or eccodes.codes_get(gid,'latitudeOfFirstGridPointInDegrees')!=90:raise ValueError('unexpected GFS grid')
    arr=eccodes.codes_get_array(gid,'values').reshape(nj,ni)
    out=[]
    for s in stations:
        y=(90-s['lat'])*4;x=(s['lon']%360)*4;i=int(y);j=int(x);a=y-i;b=x-j
        out.append(float((1-a)*(1-b)*arr[i,j]+a*(1-b)*arr[i+1,j]+(1-a)*b*arr[i,j+1]+a*b*arr[i+1,j+1]))
    return out
def one_hour(init,lead,stations):
    url=URL.format(ymd=init.strftime('%Y%m%d'),hh=init.strftime('%H'),lead=lead)
    entries=[]
    for line in get(url+'.idx').text.splitlines():
        p=line.split(':');entries.append((int(p[1]),p[3],p[4]))
    fields=[]
    for key in ('UGRD','VGRD'):
        k=next(k for k,(_,var,height) in enumerate(entries) if var==key and height=='10 m above ground')
        lo=entries[k][0];hi=entries[k+1][0]-1
        r=get(url,headers={'Range':f'bytes={lo}-{hi}'})
        if r.status_code!=206 or len(r.content)!=hi-lo+1:raise ValueError('S3 Range failed')
        gid=eccodes.codes_new_from_message(r.content)
        try: fields.append(sample(gid,stations))
        finally:eccodes.codes_release(gid)
    return [[s['station'],init.isoformat(),lead,fields[0][i],fields[1][i]] for i,s in enumerate(stations)]
def forecasts():
    stations=json.loads((ROOT/'stations.json').read_text())
    times=pd.date_range('2021-12-31T18:00:00Z','2022-12-31T18:00:00Z',freq='6h')
    folder=ROOT/'gfs_train';folder.mkdir(exist_ok=True)
    for index,init_ts in enumerate(times):
        init=init_ts.to_pydatetime();p=folder/(init.strftime('%Y%m%d%H')+'.csv')
        if p.exists():continue
        t=time.monotonic();rows=[]
        try:
            with ThreadPoolExecutor(max_workers=6) as pool:
                for future in as_completed([pool.submit(one_hour,init,h,stations) for h in range(19)]):rows.extend(future.result())
            if len(rows)!=19*len(stations):raise ValueError('incomplete rows')
            q=p.with_suffix('.partial');pd.DataFrame(rows,columns=['site','init_utc','fhr','u','v']).to_csv(q,index=False);q.rename(p)
            with (ROOT/'increment.jsonl').open('a') as f:f.write(json.dumps({'init':init.isoformat(),'seconds':round(time.monotonic()-t,2),'done':index+1,'total':len(times)})+'\n')
            if index%10==0:print('GFS_TRAIN',index+1,len(times),round(time.monotonic()-t,2),flush=True)
        except Exception as e:
            with (ROOT/'errors.jsonl').open('a') as f:f.write(json.dumps({'init':init.isoformat(),'error':traceback.format_exc()})+'\n')
            print('ERROR',init,e,flush=True)
    print('GFS_TRAIN_DONE',len(list(folder.glob('*.csv'))),len(times),flush=True)
def observations():
    folder=ROOT/'obs_train';folder.mkdir(exist_ok=True)
    for month in pd.date_range('2022-01-01','2022-12-01',freq='MS',tz='UTC'):
        p=folder/(month.strftime('%Y%m')+'.csv')
        if p.exists():continue
        end=month+pd.DateOffset(months=1)
        par={'station':','.join(STATIONS),'sts':(month-pd.Timedelta(hours=10)).strftime('%Y-%m-%dT%H:%MZ'),'ets':(end+pd.Timedelta(hours=10)).strftime('%Y-%m-%dT%H:%MZ'),'tz':'UTC','what':'download','delim':'comma','sample':'1min','vars':'sknt,drct,gust_sknt'}
        r=get(OBS,params=par)
        df=pd.read_csv(io.StringIO(r.text))
        if 'valid(UTC)' not in df:raise ValueError('IEM columns '+str(df.columns))
        df['valid_end_utc']=pd.to_datetime(df['valid(UTC)'],utc=True,errors='coerce').dt.ceil('10min')
        df['sknt']=pd.to_numeric(df.sknt,errors='coerce');df['speed_ms']=df.sknt.where(df.sknt>=0)*KNOT
        df=df[(df.valid_end_utc>=month)&(df.valid_end_utc<end)&df.station.isin(STATIONS)].copy()
        # Deduplicate timestamps per station; the interface defines >=8 of ten 1-minute samples.
        df=df.drop_duplicates(['station','valid(UTC)'])
        agg=df.groupby(['station','valid_end_utc']).agg(speed_ms=('speed_ms','mean'),count=('speed_ms','count')).reset_index()
        agg=agg[agg['count']>=8]
        q=p.with_suffix('.partial');agg.to_csv(q,index=False);q.rename(p)
        print('OBS_TRAIN',month.strftime('%Y%m'),len(df),len(agg),flush=True)
    print('OBS_TRAIN_DONE',flush=True)
def fit():
    forecasts=pd.concat([pd.read_csv(p) for p in sorted((ROOT/'gfs_train').glob('*.csv'))],ignore_index=True)
    obs=pd.concat([pd.read_csv(p) for p in sorted((ROOT/'obs_train').glob('*.csv'))],ignore_index=True)
    forecasts['init_utc']=pd.to_datetime(forecasts.init_utc,utc=True)
    forecasts['valid_hour']=forecasts.init_utc+pd.to_timedelta(forecasts.fhr,unit='h')
    fc=forecasts.set_index(['site','init_utc','valid_hour'])[['u','v']]
    obs['valid_end_utc']=pd.to_datetime(obs.valid_end_utc,utc=True)
    lookup=obs.set_index(['station','valid_end_utc']).speed_ms
    rows=[]
    for site in STATIONS:
        for issue in pd.date_range('2022-01-01T00:00Z','2022-12-31T17:00Z',freq='h'):
            init=issue.floor('6h')-pd.Timedelta(hours=6) if issue.hour%6<4 else issue.floor('6h')
            for lead in (10,20,30,60,120,180,240,300,360):
                valid=issue+pd.Timedelta(minutes=lead);mid=valid-pd.Timedelta(minutes=5)
                y=lookup.get((site,valid),np.nan)
                f0=mid.floor('h');f1=f0+pd.Timedelta(hours=1)
                v0=fc.loc[(site,init,f0)] if (site,init,f0) in fc.index else None
                v1=fc.loc[(site,init,f1)] if (site,init,f1) in fc.index else None
                if v0 is None or v1 is None or not np.isfinite(y):continue
                alpha=(mid-f0).total_seconds()/3600
                raw=float(np.hypot(*(v0*(1-alpha)+v1*alpha)))
                age=(mid-init).total_seconds()/3600
                bucket=0 if age<=6 else 1 if age<=12 else 2
                rows.append((site,issue,lead,float(y),raw,bucket))
    train=pd.DataFrame(rows,columns=['site','issue_utc','lead_min','obs','raw','bucket'])
    train.to_parquet(ROOT/'train_pairs.parquet',index=False)
    coefficients={}
    for (site,bucket),g in train.groupby(['site','bucket']):
        if len(g)<200:raise ValueError('too few training pairs '+str((site,bucket,len(g))))
        b,a=np.polyfit(g.raw.to_numpy(),g.obs.to_numpy(),1)
        coefficients[f'{site}:{bucket}']={'a':float(a),'b':float(b),'n':len(g)}
    (ROOT/'coefficients.json').write_text(json.dumps(coefficients,indent=2))
    print('F_FIT_DONE',len(train),coefficients,flush=True)
def main():
    a=argparse.ArgumentParser();a.add_argument('step',choices=['obs','gfs','fit']);args=a.parse_args()
    {'obs':observations,'gfs':forecasts,'fit':fit}[args.step]()
if __name__=='__main__':main()
