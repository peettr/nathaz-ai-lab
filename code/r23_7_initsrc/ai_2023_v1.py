#!/usr/bin/env python3
"""Two 2023 AIWP IFS archives, station range reads; immutable per-cycle ledger/checkpoints."""
import json,time,sys
from pathlib import Path
import numpy as np,pandas as pd
sys.path.insert(0,'/content/r237_m2')
import run_forecasts as old
old.LEADS=(24,48)
ROOT=Path('/content/r237_m2')
COLS=['station','init_utc','lead_h','source','fc_u','fc_v','fc_u100','fc_v100']
def save(path,thing):
    with path.open('x') as f:json.dump(thing,f,indent=2)
def run(source):
    stations=pd.read_csv(ROOT/'stations.csv')
    inits=pd.date_range('2023-01-01','2024-01-01',freq='12h',inclusive='left',tz='UTC')
    assert len(stations)==12 and len(inits)==730
    rows=[];ledger=[];start=time.monotonic()
    for n,init in enumerate(inits,1):
        t=time.monotonic();url=old.AIURL.format(source=source,year=2023,mmdd=init.strftime('%m%d'),date=init.strftime('%Y%m%d%H'))
        item={'source':source,'init_utc':init.isoformat(),'url':url}
        try:
            rr,_,size=old.ai(init,source,stations)
            assert len(rr)==24 and set(x[2] for x in rr)=={24,48}
            rows.extend(rr);item.update(status='ok',object_size=size,station_rows=len(rr))
        except Exception as e:
            item.update(status='missing' if ('404' in str(e) or 'NoSuchKey' in str(e)) else 'error',error=repr(e))
            print('ERROR',source,init,repr(e),flush=True)
        item['seconds']=time.monotonic()-t;ledger.append(item)
        if n%20==0 or n==1:
            print('PROGRESS',source,n,730,'ok',sum(z['status']=='ok' for z in ledger),'wall',time.monotonic()-start,flush=True)
        if n%50==0:
            save(ROOT/f'{source}_ledger_{n:03}_v1.json',ledger)
            with (ROOT/f'{source}_rows_{n:03}_v1.csv.gz').open('xb') as f:pd.DataFrame(rows,columns=COLS).to_csv(f,index=False,compression='gzip')
    summary={'source':source,'expected':730,'ok':sum(z['status']=='ok' for z in ledger),'missing':sum(z['status']=='missing' for z in ledger),'error':sum(z['status']=='error' for z in ledger),'wall_seconds':time.monotonic()-start,'ledger':ledger}
    save(ROOT/f'{source}_ledger_v1.json',summary)
    with (ROOT/f'{source}_station_v1.csv.gz').open('xb') as f:pd.DataFrame(rows,columns=COLS).to_csv(f,index=False,compression='gzip')
    print('DONE',source,summary['ok'],summary['missing'],summary['error'],summary['wall_seconds'],flush=True)
if __name__=='__main__':
    assert len(sys.argv)==2 and sys.argv[1] in ('GRAP_v100_IFS','PANG_v100_IFS')
    run(sys.argv[1])
