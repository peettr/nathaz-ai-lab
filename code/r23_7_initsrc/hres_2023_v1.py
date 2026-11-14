#!/usr/bin/env python3
"""ECMWF 2023 HRES open-data 10u/10v, GRIB index + HTTP Range, site vectors only."""
import argparse,json,time
from pathlib import Path
import numpy as np,pandas as pd,requests,eccodes
ROOT=Path('/content/r237_m2');BASE='https://d2zvc0wgha4k2l.cloudfront.net'
COLS=['station','init_utc','lead_h','source','fc_u','fc_v','fc_u100','fc_v100']
S=requests.Session();S.headers.update({'User-Agent':'PETW-R23.7 research station verification'})
def url(init,lead):
    date=init.strftime('%Y%m%d');hh=init.strftime('%H');return f'{BASE}/{date}/{hh}z/0p4-beta/oper/{date}{hh}0000-{lead}h-oper-fc.grib2'
def get(url,headers=None):
    r=S.get(url,headers=headers,timeout=45)
    if r.status_code not in (200,206):raise RuntimeError(f'HTTP {r.status_code} {url}')
    if headers and (r.status_code!=206 or len(r.content)>5_000_000):raise RuntimeError(f'RANGE_NOT_HONORED {url}')
    return r
def sample(message,stations):
    gid=eccodes.codes_new_from_message(message)
    try:
        param=eccodes.codes_get(gid,'shortName');ni=eccodes.codes_get(gid,'Ni');nj=eccodes.codes_get(gid,'Nj')
        lat0=float(eccodes.codes_get(gid,'latitudeOfFirstGridPointInDegrees'));lon0=float(eccodes.codes_get(gid,'longitudeOfFirstGridPointInDegrees'))
        di=float(eccodes.codes_get(gid,'iDirectionIncrementInDegrees'));dj=float(eccodes.codes_get(gid,'jDirectionIncrementInDegrees'))
        jpos=int(eccodes.codes_get(gid,'jScansPositively'));ipos=int(eccodes.codes_get(gid,'iScansNegatively'))
        if param not in ('10u','10v') or (ni,nj)!=(900,451) or abs(di-.4)>1e-4 or abs(dj-.4)>1e-4:raise ValueError((param,ni,nj,di,dj))
        grid=eccodes.codes_get_array(gid,'values').reshape(nj,ni)
        values=[]
        for s in stations.itertuples():
            # Verify orientation from GRIB flags, not from WB2's 2022 ascending axis.
            yy=(s.lat-lat0)/(dj if jpos else -dj);xx=((s.lon%360-lon0)%(360))/(di if not ipos else -di)
            iy=int(np.floor(yy));ix=int(np.floor(xx));a=yy-iy;b=xx-ix
            if not (0<=iy<nj-1 and 0<=ix<ni-1):raise ValueError((s.station,yy,xx))
            q=grid[iy:iy+2,ix:ix+2]
            values.append(float((1-a)*(1-b)*q[0,0]+a*(1-b)*q[1,0]+(1-a)*b*q[0,1]+a*b*q[1,1]))
        return values,{'name':param,'Ni':ni,'Nj':nj,'first_lat':lat0,'first_lon':lon0,'di':di,'dj':dj,'jScansPositively':jpos,'iScansNegatively':ipos}
    finally:eccodes.codes_release(gid)
def run(stage):
    stations=pd.read_csv(ROOT/'stations.csv')
    inits=pd.date_range('2023-01-18','2024-01-01',freq='12h',inclusive='left',tz='UTC')
    assert len(inits)==696 and len(stations)==12
    month=inits[inits.month==1];inits=month if stage=='pilot' else inits[inits.month!=1]
    assert len(inits)==(28 if stage=='pilot' else 668)
    rows=[];ledger=[];start=time.monotonic();metadata=None
    for n,init in enumerate(inits,1):
        t=time.monotonic();entry={'init_utc':init.isoformat(),'source':'HRES_OpenData_0p4-beta','urls':[],'range_bytes':0}
        try:
            bylead={}
            for lead in (24,48):
                u=url(init,lead);entry['urls'].append(u)
                records=[json.loads(x) for x in get(u.replace('.grib2','.index')).text.splitlines()]
                assert len(records)>2
                pair={x['param']:x for x in records if x.get('param') in ('10u','10v') and x.get('levtype')=='sfc'}
                if set(pair)!= {'10u','10v'}:raise ValueError((u,list(pair)))
                vectors=[]
                for param in ('10u','10v'):
                    item=pair[param];startbyte=int(item['_offset']);length=int(item['_length'])
                    assert 0<length<5_000_000
                    response=get(u,{'Range':f'bytes={startbyte}-{startbyte+length-1}'})
                    assert len(response.content)==length
                    vals,meta=sample(response.content,stations)
                    assert meta['name']==param
                    entry['range_bytes']+=length;vectors.append(vals)
                    if metadata is None:metadata=meta
                    else:assert all(metadata[k]==meta[k] for k in ('Ni','Nj','first_lat','first_lon','di','dj','jScansPositively','iScansNegatively'))
                bylead[lead]=vectors
            for lead in (24,48):
                uu,vv=bylead[lead]
                for s,u,v in zip(stations.station,uu,vv):rows.append((s,init.isoformat(),lead,'HRES',u,v,np.nan,np.nan))
            entry.update(status='ok',station_rows=24)
        except Exception as e:
            entry.update(status='missing' if '404' in str(e) else 'error',error=repr(e))
            print('ERROR',init.isoformat(),repr(e),flush=True)
        entry['seconds']=time.monotonic()-t;ledger.append(entry)
        if n%10==0 or n==1:print('HRES_PROGRESS',stage,n,len(inits),'ok',sum(x['status']=='ok' for x in ledger),'elapsed',time.monotonic()-start,flush=True)
        if n%50==0:
            with (ROOT/f'HRES_{stage}_{n:03}_ledger_v1.json').open('x') as f:json.dump(ledger,f)
            with (ROOT/f'HRES_{stage}_{n:03}_rows_v1.csv.gz').open('xb') as f:pd.DataFrame(rows,columns=COLS).to_csv(f,index=False,compression='gzip')
    summary={'stage':stage,'expected':len(inits),'ok':sum(x['status']=='ok' for x in ledger),'missing':sum(x['status']=='missing' for x in ledger),'error':sum(x['status']=='error' for x in ledger),'wall_seconds':time.monotonic()-start,'grid':metadata,'variable_names':['10u','10v'],'lead_hours':[24,48],'ledger':ledger}
    with (ROOT/f'HRES_{stage}_ledger_v1.json').open('x') as f:json.dump(summary,f,indent=2)
    with (ROOT/f'HRES_{stage}_station_v1.csv.gz').open('xb') as f:pd.DataFrame(rows,columns=COLS).to_csv(f,index=False,compression='gzip')
    print('HRES_DONE',stage,summary['ok'],summary['missing'],summary['error'],summary['wall_seconds'],metadata,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['pilot','remainder']);run(p.parse_args().stage)
