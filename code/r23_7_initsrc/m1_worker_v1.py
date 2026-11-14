#!/usr/bin/env python3
"""R23.7 M1; 2022-only IFS extraction and old GFS reproduction.
Never opens 2023 IFS or HRES. Run on Colab CPU; write only /content/r237m1v1.
"""
import argparse, json, time, traceback, importlib.util
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path('/content/r237m1v1')
OLD='/content/r237_old'
SOURCES=('GRAP_v100_IFS','PANG_v100_IFS')

def write_new(p,data):
    with p.open('x') as f:f.write(data)

def lin(x,y):
    m=np.isfinite(x)&np.isfinite(y)
    if m.sum()<12:return [float(np.nanmean(y[m])),0.] if m.any() else [np.nan,np.nan]
    if np.std(x[m])<1e-8:return [float(np.mean(y[m])),0.]
    b,a=np.polyfit(x[m],y[m],1)
    return [float(a),float(b)]

def reproduce():
    from collections import OrderedDict
    train=pd.read_csv(OLD+'/paired_station_train.csv.gz')
    test=pd.read_csv(OLD+'/paired_station_test.csv.gz')
    wanted=['GRAP_v100_GFS','PANG_v100_GFS','GFS']
    result={}
    for src in wanted:
        a=train[(train.source==src)&train.lead_h.eq(24)].copy()
        b=test[(test.source==src)&test.lead_h.eq(24)].copy()
        fits={}
        for station,g in a.groupby('station'):
            fits[station]=lin(np.hypot(g.fc_u.to_numpy(),g.fc_v.to_numpy()),g.metar_speed.to_numpy())
        b['refit']=np.nan
        for station,g in b.groupby('station'):
            coef=fits[station]
            b.loc[g.index,'refit']=np.maximum(0,coef[0]+coef[1]*np.hypot(g.fc_u.to_numpy(),g.fc_v.to_numpy()))
        actual=float(np.abs(b.refit-b.metar_speed).mean())
        old=float(np.abs(b.corrected-b.metar_speed).mean())
        deviation=float(np.max(np.abs(b.refit-b.corrected)))
        result[src]={'n':len(b),'refit_mae':actual,'archive_mae':old,'difference':actual-old,'max_row_diff':deviation,'train_n':len(a),'coefficients':fits}
    expected=json.load(open(OLD+'/metrics_v2.json'))['reproduction']
    result['expected_7917']=expected['paired_cases']
    result['pass']=all(result[s]['n']==7917 and abs(result[s]['difference'])<=0.002 for s in wanted)
    write_new(ROOT/'reproduction_v1.json',json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False))
    print('REPRODUCTION',json.dumps({s:{k:v for k,v in result[s].items() if k!='coefficients'} for s in wanted}),'PASS',result['pass'],flush=True)
    if not result['pass']:raise RuntimeError('Reproduction gate failed; stop')

def collect(source):
    import run_forecasts as old
    old.LEADS=(24,48)
    stations=pd.read_csv(OLD+'/stations.csv')
    inits=pd.date_range('2022-01-01','2023-01-01',freq='12h',inclusive='left',tz='UTC')
    inits=inits[inits.day<=15]
    assert len(inits)==360 and len(stations)==12
    out=ROOT/source;out.mkdir(exist_ok=False)
    rows=[];ledger=[];start=time.monotonic()
    for i,init in enumerate(inits,1):
        t=time.monotonic()
        url=old.AIURL.format(source=source,year=2022,mmdd=init.strftime('%m%d'),date=init.strftime('%Y%m%d%H'))
        item={'source':source,'init_utc':init.isoformat(),'url':url}
        try:
            rr,actual_url,size=old.ai(init,source,stations)
            assert len(rr)==24
            rows.extend(rr)
            item.update(status='ok',object_size=size,station_rows=len(rr))
        except Exception as exc:
            item.update(status='missing' if ('404' in str(exc) or 'NoSuchKey' in str(exc)) else 'error',error=repr(exc))
            print('OBJECT_ERROR',source,init.isoformat(),repr(exc),flush=True)
        item['seconds']=time.monotonic()-t
        ledger.append(item)
        if i%10==0 or i==1:print('PROGRESS',source,i,360,'ok',sum(x['status']=='ok' for x in ledger),'seconds',round(time.monotonic()-start,2),flush=True)
        if i%20==0:
            # Incremental recovery files, unique names; no replacements of prior checkpoints.
            write_new(out/f'ledger_{i:03}.json',json.dumps(ledger,indent=2))
            pd.DataFrame(rows,columns=['station','init_utc','lead_h','source','fc_u','fc_v','fc_u100','fc_v100']).to_csv(out/f'rows_{i:03}.csv.gz',index=False,compression='gzip')
    summary={'source':source,'expected_objects':360,'ok':sum(x['status']=='ok' for x in ledger),'missing':sum(x['status']=='missing' for x in ledger),'error':sum(x['status']=='error' for x in ledger),'rows':len(rows),'object_seconds_sum':sum(x['seconds'] for x in ledger),'wall_seconds':time.monotonic()-start,'ledger':ledger}
    write_new(ROOT/f'{source}_ledger_v1.json',json.dumps(summary,indent=2))
    df=pd.DataFrame(rows,columns=['station','init_utc','lead_h','source','fc_u','fc_v','fc_u100','fc_v100'])
    with (ROOT/f'{source}_station_v1.csv.gz').open('xb') as f:df.to_csv(f,index=False,compression='gzip')
    print('SOURCE_DONE',source,json.dumps({k:v for k,v in summary.items() if k!='ledger'}),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['reproduce','collect']);p.add_argument('--source',choices=SOURCES);a=p.parse_args()
    ROOT.mkdir(exist_ok=True)
    if a.stage=='reproduce':reproduce()
    else:
        if not (ROOT/'reproduction_v1.json').exists() or not json.load(open(ROOT/'reproduction_v1.json'))['pass']:raise RuntimeError('Reproduction gate not passed')
        if not a.source:raise ValueError('source required')
        collect(a.source)
if __name__=='__main__':main()
