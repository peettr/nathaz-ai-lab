#!/usr/bin/env python3
"""M4 archive collector: one immutable CSV per forecast init, monthly OKC obs.
Run on Colab CPU; independent of scorer. Never overwrite a complete file.
"""
import argparse, json, time, io, traceback
from pathlib import Path
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from m4_training import one_hour, get, OBS, KNOT
ROOT=Path('/content/m4')
PERIODS={('OKC','train'):('2022-01-01','2023-01-01'),('OKC','test'):('2023-01-01','2024-01-01'),('Swiss','train'):('2023-10-01','2024-01-01'),('Swiss','test'):('2024-01-01','2024-04-01')}
def collect_gfs(net,split):
    start,end=PERIODS[net,split]
    # The previous 18h can provide the latest cycle at the earliest issue.
    times=pd.date_range(pd.Timestamp(start,tz='UTC')-pd.Timedelta(hours=18),pd.Timestamp(end,tz='UTC'),freq='6h',inclusive='left')
    stations=json.loads((ROOT/f'{net}_stations.json').read_text())
    folder=ROOT/net/f'gfs_{split}';folder.mkdir(parents=True,exist_ok=True)
    errors=ROOT/net/f'gfs_{split}_errors.jsonl'
    for index,t in enumerate(times,1):
        init=t.to_pydatetime();p=folder/(init.strftime('%Y%m%d%H')+'.csv')
        if p.exists():continue
        try:
            rows=[]
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures=[pool.submit(one_hour,init,h,stations) for h in range(19)]
                for future in as_completed(futures):rows.extend(future.result())
            if len(rows)!=19*len(stations):raise ValueError('incomplete init')
            tmp=p.with_suffix('.partial')
            pd.DataFrame(rows,columns=['site','init_utc','fhr','u','v']).to_csv(tmp,index=False)
            tmp.rename(p)
        except Exception:
            with errors.open('a') as f:f.write(json.dumps({'init':init.isoformat(),'error':traceback.format_exc()})+'\n')
        if index%10==0:print('GFS',net,split,index,len(times),'complete',len(list(folder.glob('*.csv'))),flush=True)
    print('GFS_DONE',net,split,len(list(folder.glob('*.csv'))),len(times),flush=True)
def collect_okc_obs(split):
    start,end=PERIODS['OKC',split]
    stations=['GOK','OKC','PWA']
    folder=ROOT/'OKC'/f'obs_{split}';folder.mkdir(parents=True,exist_ok=True)
    for month in pd.date_range(start,end,freq='MS',inclusive='left',tz='UTC'):
        p=folder/(month.strftime('%Y%m')+'.csv')
        if p.exists():continue
        last=min(month+pd.DateOffset(months=1),pd.Timestamp(end,tz='UTC'))
        par={'station':','.join(stations),'sts':(month-pd.Timedelta(hours=10)).strftime('%Y-%m-%dT%H:%MZ'),'ets':(last+pd.Timedelta(hours=10)).strftime('%Y-%m-%dT%H:%MZ'),'tz':'UTC','what':'download','delim':'comma','sample':'1min','vars':'sknt,drct,gust_sknt'}
        r=get(OBS,params=par)
        df=pd.read_csv(io.StringIO(r.text))
        if 'valid(UTC)' not in df:raise ValueError('IEM schema '+str(df.columns))
        df['valid_end_utc']=pd.to_datetime(df['valid(UTC)'],utc=True,errors='coerce').dt.ceil('10min')
        df['sknt']=pd.to_numeric(df.sknt,errors='coerce')
        df['speed_ms']=df.sknt.where(df.sknt>=0)*KNOT
        df=df[(df.valid_end_utc>=month)&(df.valid_end_utc<last)&df.station.isin(stations)].drop_duplicates(['station','valid(UTC)'])
        agg=df.groupby(['station','valid_end_utc']).agg(speed_ms=('speed_ms','mean'),count=('speed_ms','count')).reset_index()
        agg=agg[agg['count']>=8]
        q=p.with_suffix('.partial');agg.to_csv(q,index=False);q.rename(p)
        print('OKC_OBS',split,month.strftime('%Y%m'),len(agg),flush=True)
def main():
    a=argparse.ArgumentParser();a.add_argument('task',choices=['gfs','okc_obs']);a.add_argument('net',choices=['OKC','Swiss']);a.add_argument('split',choices=['train','test']);x=a.parse_args()
    if x.task=='gfs':collect_gfs(x.net,x.split)
    elif x.net=='OKC':collect_okc_obs(x.split)
    else:raise ValueError('Swiss obs supplied from frozen local CSV')
if __name__=='__main__':main()
