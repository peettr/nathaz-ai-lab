#!/usr/bin/env python3
"""M5 Swiss test-period GFS extraction and time-aligned paired table; Colab only.
Must not be launched until scorer/config hashes are recorded in BOTH experiment cards.
"""
import csv,json,os,sys,time,traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import pandas as pd
import numpy as np
from m5_training import ROOT,STATIONS,FHRS,PREV,hour,features

def stage():
    folder=ROOT/'test_gfs';folder.mkdir(exist_ok=True)
    dates=pd.date_range('2023-12-30T00:00:00Z','2024-03-31T18:00:00Z',freq='6h')
    for seq,stamp in enumerate(dates,1):
        init=stamp.to_pydatetime();p=folder/f'{init:%Y%m%d%H}.csv'
        if p.exists():continue
        # Only training-period forecasts from the immutable, successful stage are reused.
        earlier=ROOT/'train_gfs'/p.name
        if earlier.exists():
            import shutil
            shutil.copyfile(earlier,p)
            continue
        t=time.monotonic()
        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                fs={pool.submit(hour,init,h):h for h in sorted(set(PREV.values())|set(FHRS))}
                data={fs[f]:f.result() for f in as_completed(fs)}
            rows=[]
            for fhr in FHRS:
                mid=fhr-1/12;alpha=(mid-PREV[fhr])/(fhr-PREV[fhr])
                for site,raw,v1,zs,dz in features(data[PREV[fhr]],data[fhr],alpha):rows.append((site,init.isoformat(),fhr,raw,v1,zs,dz))
            q=p.with_suffix('.partial')
            with q.open('w') as w:
                cw=csv.writer(w);cw.writerow(['site','init_utc','fhr','raw','v1','z_model_sfc','dz']);cw.writerows(rows)
            q.rename(p)
            with (ROOT/'test_progress.jsonl').open('a') as w:w.write(json.dumps({'init':init.isoformat(),'done':seq,'total':len(dates),'seconds':round(time.monotonic()-t,2)})+'\n')
            if seq%5==0:print('TEST_GFS',seq,len(dates),round(time.monotonic()-t,2),flush=True)
        except Exception as e:
            with (ROOT/'test_errors.jsonl').open('a') as w:w.write(json.dumps({'init':init.isoformat(),'error':traceback.format_exc()})+'\n')
            print('TEST_ERROR',init,repr(e),flush=True)
    if len(list(folder.glob('*.csv')))!=len(dates):raise RuntimeError('incomplete test GFS')
    print('TEST_GFS_DONE',len(dates),flush=True)

def pair():
    paths=sorted((ROOT/'test_gfs').glob('*.csv'))
    expected=len(pd.date_range('2023-12-30T00:00Z','2024-03-31T18:00Z',freq='6h'))
    if len(paths)!=expected:raise ValueError('incomplete test GFS '+str(len(paths)))
    fc=pd.concat(map(pd.read_csv,paths),ignore_index=True)
    fc['init_utc']=pd.to_datetime(fc.init_utc,utc=True)
    fc['valid_end_utc']=fc.init_utc+pd.to_timedelta(fc.fhr,unit='h')
    fc=fc[(fc.valid_end_utc>=pd.Timestamp('2024-01-01',tz='UTC'))&(fc.valid_end_utc<pd.Timestamp('2024-04-01',tz='UTC'))]
    obs=pd.concat([pd.read_csv(p,usecols=['station','time_utc','speed_ms']) for p in sorted((ROOT/'obs').glob('obs_*.csv'))],ignore_index=True)
    obs=obs.rename(columns={'station':'site','time_utc':'valid_end_utc','speed_ms':'obs'})
    obs.valid_end_utc=pd.to_datetime(obs.valid_end_utc,utc=True)
    obs=obs[(obs.valid_end_utc>=pd.Timestamp('2024-01-01',tz='UTC'))&(obs.valid_end_utc<pd.Timestamp('2024-04-01',tz='UTC'))]
    merged=fc.merge(obs,on=['site','valid_end_utc'],how='inner').dropna(subset=['obs','raw','v1','dz'])
    merged['terrain']=merged.site.map({s['site']:s['terrain'] for s in STATIONS})
    if len(merged)<10000:raise ValueError('too few test pairs '+str(len(merged)))
    merged.to_parquet(ROOT/'test_pairs.parquet',index=False)
    print('TEST_PAIR_DONE',len(merged),flush=True)
if __name__=='__main__':{'gfs':stage,'pair':pair}[sys.argv[1]]()
