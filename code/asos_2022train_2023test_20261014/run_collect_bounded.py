#!/usr/bin/env python3
"""Resume 2022 24/48h station-only AIWP/GFS retrieval in bounded concurrent batches."""
import argparse, concurrent.futures, json, os, time, traceback, threading
from pathlib import Path
import pandas as pd
import run_forecasts as rf
rf.LEADS=(24,48)
SOURCES=('FOUR_v200_GFS','PANG_v100_GFS','GRAP_v100_GFS','GFS')
def task(pair,stations,root):
    source,init=pair; stem=f'{source}_{init:%Y%m%d%H}'; folder=root/'2022'/source
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/(stem+'.csv');meta=folder/(stem+'.json');err=folder/(stem+'.error')
    if path.exists() and meta.exists():
        if {24,48}.issubset(set(pd.read_csv(path).lead_h)) and len(pd.read_csv(path)) in (len(stations)*2,len(stations)*6):return 'SKIP',stem,0
        return 'MISMATCH',stem,0
    if path.exists() or meta.exists():return 'PARTIAL',stem,0
    t=time.monotonic()
    try:
        rows,url,nbytes=rf.gfs(init,stations) if source=='GFS' else rf.ai(init,source,stations)
        assert len(rows)==len(stations)*2
        df=pd.DataFrame(rows,columns=['station','init_utc','lead_h','source','fc_u','fc_v','fc_u100','fc_v100'])
        text=df.to_csv(index=False);tmp=path.with_suffix('.part');tmp.write_text(text);os.replace(tmp,path)
        m={'source':source,'init':init.isoformat(),'url':url,'source_object_bytes_or_gfs_range_bytes':nbytes,'station_rows':len(df),'seconds':time.monotonic()-t,'csv_bytes':len(text.encode())}
        tmp=meta.with_suffix('.part');tmp.write_text(json.dumps(m));os.replace(tmp,meta)
        return 'OK',stem,m['seconds']
    except Exception:
        err.write_text(traceback.format_exc());return 'ERROR',stem,time.monotonic()-t
def main():
    p=argparse.ArgumentParser();p.add_argument('--stations',required=True);p.add_argument('--out',required=True);p.add_argument('--workers',type=int,default=16);p.add_argument('--days',type=int,default=31);p.add_argument('--months',nargs='+',type=int,default=list(range(1,13)));p.add_argument('--sources',nargs='+',default=list(SOURCES));a=p.parse_args()
    root=Path(a.out);root.mkdir(parents=True,exist_ok=True);stations=pd.read_csv(a.stations)
    pairs=[(s,d) for m in a.months for d in pd.date_range(f'2022-{m:02}-01',periods=min(a.days,pd.Period(f'2022-{m:02}').days_in_month)*2,freq='12h',tz='UTC') for s in a.sources]
    counts={};start=time.monotonic();done=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
        fs={ex.submit(task,pair,stations,root):pair for pair in pairs}
        for fut in concurrent.futures.as_completed(fs):
            status,stem,sec=fut.result();done+=1;counts[status]=counts.get(status,0)+1
            if status not in ('OK','SKIP') or done%20==0:
                print('PROGRESS',done,len(pairs),counts,stem,round(time.monotonic()-start,1),flush=True)
            if done%20==0 or done==len(pairs):
                tmp=root/'progress.part';tmp.write_text(json.dumps({'done':done,'total':len(pairs),'counts':counts,'seconds':time.monotonic()-start,'last':stem}));os.replace(tmp,root/'progress.json')
    print('COLLECT_DONE',len(pairs),counts,flush=True)
if __name__=='__main__':main()
