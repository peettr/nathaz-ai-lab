#!/usr/bin/env python3
"""Range-select station forecasts for training year and missing test-year sources.
Run on Colab. Writes append-only per-object station CSV and metadata; no grid fields.
"""
import argparse, concurrent.futures, json, os, time, traceback
from pathlib import Path
import pandas as pd
from run_forecasts import ai, gfs, LEADS

AI=['FOUR_v200_GFS','PANG_v100_GFS','GRAP_v100_GFS','FOUR_v200_IFS','PANG_v100_IFS','GRAP_v100_IFS']

def task(pair, stations, root):
    source,init=pair
    stem=f'{source}_{init:%Y%m%d%H}'
    folder=root/str(init.year)/source
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/(stem+'.csv'); meta=folder/(stem+'.json'); err=folder/(stem+'.error')
    if path.exists() and meta.exists(): return ('SKIP',stem,0)
    if path.exists() or meta.exists():return ('PARTIAL',stem,0)
    t=time.monotonic()
    try:
        rows,url,nbytes=gfs(init,stations) if source=='GFS' else ai(init,source,stations)
        assert len(rows)==len(stations)*len(LEADS)
        df=pd.DataFrame(rows,columns=['station','init_utc','lead_h','source','fc_u','fc_v','fc_u100','fc_v100'])
        text=df.to_csv(index=False)
        tmp=path.with_suffix('.part'); tmp.write_text(text); os.replace(tmp,path)
        meta.write_text(json.dumps({'source':source,'init':init.isoformat(),'url':url,'object_size_or_gfs_transferred_bytes':nbytes,'station_rows':len(df),'seconds':time.monotonic()-t,'csv_bytes':len(text.encode())}))
        return ('OK',stem,time.monotonic()-t)
    except Exception:
        err.write_text(traceback.format_exc())
        return ('ERROR',stem,time.monotonic()-t)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--stations',required=True);p.add_argument('--out',required=True)
    p.add_argument('--train-year',type=int,default=2022);p.add_argument('--test-year',type=int,default=2023)
    p.add_argument('--sources-train',nargs='+',default=AI+['GFS']);p.add_argument('--sources-test',nargs='+',default=AI[3:])
    p.add_argument('--workers',type=int,default=12);p.add_argument('--limit-inits',type=int,default=0)
    a=p.parse_args();stations=pd.read_csv(a.stations);root=Path(a.out);root.mkdir(parents=True,exist_ok=True)
    pairs=[]
    for year,sources in [(a.train_year,a.sources_train),(a.test_year,a.sources_test)]:
        dates=pd.date_range(f'{year}-01-01',f'{year+1}-01-01',freq='12h',inclusive='left',tz='UTC')
        if a.limit_inits:dates=dates[:a.limit_inits]
        pairs.extend((s,d) for d in dates for s in sources)
    tally={}; start=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        for i,(status,stem,elapsed) in enumerate(pool.map(lambda x:task(x,stations,root),pairs),1):
            tally[status]=tally.get(status,0)+1
            if status not in ('OK','SKIP') or i%50==0:print('PROGRESS',i,len(pairs),tally,stem,round(time.monotonic()-start,1),flush=True)
    print('COLLECT_DONE',len(pairs),tally,flush=True)
if __name__=='__main__':main()
