#!/usr/bin/env python3
"""WB2 HRES 2022 only: 360 fixed cycles, 24/48 h, station bilinear sampling.
Run in the existing Colab CPU VM, retain station rows only (global chunks ephemeral).
"""
import json,time,traceback
from pathlib import Path
import numpy as np,pandas as pd,xarray as xr
ROOT=Path('/content/r237m1v2')
URL='gs://weatherbench2/datasets/hres/2016-2022-12h-6h-0p25deg-chunk-1.zarr'
NAMES=('10m_u_component_of_wind','10m_v_component_of_wind')
def put(path, content):
    with path.open('x') as f:f.write(content)
def main():
    stations=pd.read_csv('/content/r237_old/stations.csv')
    inits=pd.date_range('2022-01-01','2023-01-01',freq='12h',inclusive='left',tz='UTC')
    inits=inits[inits.day<=15]
    assert len(inits)==360 and len(stations)==12
    d=xr.open_zarr(URL,storage_options={'token':'anon'},consolidated=True,decode_timedelta=True)
    assert all(x in d for x in NAMES)
    assert np.array_equal(d.prediction_timedelta.sel(prediction_timedelta=[np.timedelta64(24,'h'),np.timedelta64(48,'h')]).values, np.array([np.timedelta64(24,'h'),np.timedelta64(48,'h')],dtype='timedelta64[ns]'))
    assert float(d.latitude[0])==-90 and float(d.longitude[0])==0
    assert all(d[x].encoding['chunks']==(1,1,721,1440) for x in NAMES)
    # WB2 latitude ascends, unlike the AIWP north-first archive.
    y=(stations.lat.to_numpy()+90)*4;x=(stations.lon.to_numpy()%360)*4
    iy=np.floor(y).astype(int);ix=np.floor(x).astype(int);a=y-iy;b=x-ix
    assert all((iy>=0)&(iy<720)&(ix>=0)&(ix<1439))
    y0=int(iy.min());y1=int(iy.max())+2;x0=int(ix.min());x1=int(ix.max())+2
    assert all(np.isin(inits.tz_localize(None).values,d.time.values))
    out=ROOT/'HRES_2022';out.mkdir(exist_ok=False)
    rows=[];ledger=[];start=time.monotonic()
    for n,init in enumerate(inits,1):
        t=time.monotonic();entry={'source':'HRES_WB2_2022','init_utc':init.isoformat(),'url':URL}
        try:
            for lead in (24,48):
                region=d[list(NAMES)].sel(time=init.tz_localize(None).to_datetime64(),prediction_timedelta=np.timedelta64(lead,'h')).isel(latitude=slice(y0,y1),longitude=slice(x0,x1)).compute()
                vectors=[]
                for name in NAMES:
                    arr=region[name].values
                    def bil(k):
                        ii=iy[k]-y0;jj=ix[k]-x0
                        return float((1-a[k])*(1-b[k])*arr[ii,jj]+a[k]*(1-b[k])*arr[ii+1,jj]+(1-a[k])*b[k]*arr[ii,jj+1]+a[k]*b[k]*arr[ii+1,jj+1])
                    vectors.append([bil(k) for k in range(len(stations))])
                if not np.isfinite(vectors).all():raise ValueError('nonfinite 10 m wind')
                for k,s in enumerate(stations.station):rows.append((s,init.isoformat(),lead,'HRES',vectors[0][k],vectors[1][k],np.nan,np.nan))
            entry.update(status='ok',station_rows=24)
        except Exception as exc:
            # Never count a partially completed initialization.
            if rows and rows[-1][1]==init.isoformat():rows=[r for r in rows if r[1]!=init.isoformat()]
            entry.update(status='missing' if '404' in str(exc) or 'NoSuchKey' in str(exc) else 'error',error=repr(exc))
            print('OBJECT_ERROR',init.isoformat(),repr(exc),flush=True)
        entry['seconds']=time.monotonic()-t;ledger.append(entry)
        if n%10==0 or n==1:print('PROGRESS HRES',n,360,'ok',sum(e['status']=='ok' for e in ledger),'seconds',round(time.monotonic()-start,2),flush=True)
        if n%20==0:
            put(out/f'ledger_{n:03}.json',json.dumps(ledger))
            with (out/f'rows_{n:03}.csv.gz').open('xb') as f:pd.DataFrame(rows,columns=['station','init_utc','lead_h','source','fc_u','fc_v','fc_u100','fc_v100']).to_csv(f,index=False,compression='gzip')
    summary={'source':'HRES_WB2_2022','expected_objects':360,'ok':sum(e['status']=='ok' for e in ledger),'missing':sum(e['status']=='missing' for e in ledger),'error':sum(e['status']=='error' for e in ledger),'rows':len(rows),'wall_seconds':time.monotonic()-start,'ledger':ledger,'variable_names':NAMES,'lead_hours':[24,48]}
    put(ROOT/'HRES_2022_ledger_v1.json',json.dumps(summary,indent=2))
    with (ROOT/'HRES_2022_station_v1.csv.gz').open('xb') as f:pd.DataFrame(rows,columns=['station','init_utc','lead_h','source','fc_u','fc_v','fc_u100','fc_v100']).to_csv(f,index=False,compression='gzip')
    print('SOURCE_DONE HRES',json.dumps({k:v for k,v in summary.items() if k!='ledger'}),flush=True)
if __name__=='__main__':main()
