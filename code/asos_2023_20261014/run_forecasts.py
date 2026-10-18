#!/usr/bin/env python3
"""Remote range-select AIWP HDF5 and GFS GRIB2 .idx, save ONLY station time series.
Example: python run_forecasts.py --stations stations.csv --year 2023 --sources FOUR_v200_GFS PANG_v100_GFS GRAP_v100_GFS GFS --out /content/a1
"""
import argparse,io,json,math,time,traceback
from pathlib import Path
import numpy as np
import pandas as pd
import requests,fsspec,h5py
S=requests.Session(); S.headers['User-Agent']='NatHaz-A1 public data research'
LEADS=(6,12,24,36,48,72)
AIURL='https://noaa-oar-mlwp-data.s3.amazonaws.com/{source}/{year}/{mmdd}/{source}_{date}_f000_f240_06.nc'
GFSURL='https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{ymd}/{hh}/atmos/gfs.t{hh}z.pgrb2.0p25.f{lead:03d}'
def interpolate(field,stations):
    vals=[]
    for x in stations.itertuples():
        iy=(90-x.lat)*4; ix=(x.lon%360)*4;i=int(np.floor(iy));j=int(np.floor(ix));a=iy-i;b=ix-j
        q=field[i:i+2,j:j+2]
        if q.shape!=(2,2):raise ValueError(f'outside grid {x.station} {field.shape}')
        vals.append(float((1-a)*(1-b)*q[0,0]+a*(1-b)*q[1,0]+(1-a)*b*q[0,1]+a*b*q[1,1]))
    return vals
def ai(init,source,stations):
    url=AIURL.format(source=source,year=init.year,mmdd=init.strftime('%m%d'),date=init.strftime('%Y%m%d%H'))
    h=fsspec.open(url,'rb',block_size=262144).open(); out=[]
    try:
        with h5py.File(h,'r') as f:
            names=['u10','v10']+(['u100','v100'] if source.startswith('FOUR') else [])
            for k in names:
                if k not in f:raise KeyError(f'{k} absent at {url}')
            for lead in LEADS:
                arr={k:f[k][lead//6,210:225,1040:1065] for k in names}
                # Interpolation expects global indices; shift station indices into the regional slice.
                local=stations.copy();local['lat']=90-((90-local.lat)*4-210)/4;local['lon']=((local.lon%360)*4-1040)/4
                # local lon can be negative; avoid modulo wrap by direct local stencil below.
                for s in stations.itertuples():
                    yi=(90-s.lat)*4-210;xi=(s.lon%360)*4-1040;i=int(np.floor(yi));j=int(np.floor(xi));a=yi-i;b=xi-j
                    if not (0<=i<14 and 0<=j<24):raise ValueError(f'outside OKC window: {s.station}')
                    def bil(k):
                        q=arr[k][i:i+2,j:j+2]
                        return float((1-a)*(1-b)*q[0,0]+a*(1-b)*q[1,0]+(1-a)*b*q[0,1]+a*b*q[1,1])
                    out.append((s.station,init.isoformat(),lead,source,bil('u10'),bil('v10'),bil('u100') if 'u100' in names else np.nan,bil('v100') if 'v100' in names else np.nan))
        size=getattr(h,'details',{}).get('size')
        return out,url,size
    finally:h.close()
def req(url,headers=None):
    for attempt in range(4):
        try:
            r=S.get(url,headers=headers,timeout=90)
            if r.status_code in (200,206):return r
            if r.status_code not in (429,500,503,504):raise RuntimeError(f'HTTP {r.status_code} {url}')
        except requests.RequestException:
            if attempt==3:raise
        time.sleep(2*(attempt+1))
    raise RuntimeError(f'Failed: {url}')
def gfs(init,stations):
    import eccodes
    out=[];bytes_count=0
    for lead in LEADS:
        url=GFSURL.format(ymd=init.strftime('%Y%m%d'),hh=init.strftime('%H'),lead=lead)
        idx=req(url+'.idx').text.splitlines();bytes_count+=sum(len(x)+1 for x in idx)
        offsets=[]
        for line in idx:
            part=line.split(':');offsets.append((int(part[1]),part[3],part[4]))
        fields={}
        for key in ['UGRD','VGRD']:
            for height in ['10 m above ground','100 m above ground']:
                pos=next((i for i,(_,k,h) in enumerate(offsets) if k==key and h==height),None)
                if pos is None:raise KeyError((url,key,height))
                a=offsets[pos][0];b=offsets[pos+1][0]-1 if pos+1<len(offsets) else None
                if b is None:raise ValueError('No next GRIB index offset')
                data=req(url,{'Range':f'bytes={a}-{b}'}).content;bytes_count+=len(data)
                gid=eccodes.codes_new_from_message(data)
                try:
                    ni=eccodes.codes_get(gid,'Ni');nj=eccodes.codes_get(gid,'Nj')
                    if (ni,nj)!=(1440,721):raise ValueError(f'GFS grid unexpected {ni} {nj}')
                    firstlat=eccodes.codes_get(gid,'latitudeOfFirstGridPointInDegrees')
                    firstlon=eccodes.codes_get(gid,'longitudeOfFirstGridPointInDegrees')
                    arr=eccodes.codes_get_array(gid,'values').reshape(nj,ni)
                    if firstlat!=90 or firstlon!=0:raise ValueError(f'GFS orientation unexpected {firstlat} {firstlon}')
                    fields[(key,height)]=interpolate(arr,stations)
                finally:eccodes.codes_release(gid)
        for n,s in enumerate(stations.itertuples()):
            out.append((s.station,init.isoformat(),lead,'GFS',fields[('UGRD','10 m above ground')][n],fields[('VGRD','10 m above ground')][n],fields[('UGRD','100 m above ground')][n],fields[('VGRD','100 m above ground')][n]))
    return out,url,bytes_count
def main():
    p=argparse.ArgumentParser();p.add_argument('--stations',required=True);p.add_argument('--year',type=int,required=True);p.add_argument('--sources',nargs='+',required=True);p.add_argument('--out',required=True);p.add_argument('--limit-inits',type=int,default=0);p.add_argument('--shard-index',type=int,default=0);p.add_argument('--shard-count',type=int,default=1);a=p.parse_args()
    stations=pd.read_csv(a.stations);out=Path(a.out);partdir=out/'forecast_parts';partdir.mkdir(parents=True,exist_ok=True)
    inits=pd.date_range(f'{a.year}-01-01',f'{a.year+1}-01-01',freq='12h',inclusive='left',tz='UTC')
    if a.limit_inits:inits=inits[:a.limit_inits]
    if not (0<=a.shard_index<a.shard_count):raise ValueError('Invalid shard')
    inits=inits[a.shard_index::a.shard_count]
    for init in inits:
        for source in a.sources:
            path=partdir/f'{source}_{init.strftime("%Y%m%d%H")}.csv';meta=partdir/f'{source}_{init.strftime("%Y%m%d%H")}.json'
            if path.exists() and meta.exists():continue
            if path.exists() or meta.exists():
                print('INCOMPLETE_EXISTING',source,init.isoformat(),'manual reconciliation required',flush=True);continue
            t=time.monotonic()
            try:
                if source=='GFS':rows,url,nbytes=gfs(init,stations)
                else:rows,url,nbytes=ai(init,source,stations)
                if len(rows)!=len(stations)*len(LEADS):raise ValueError('incomplete forecast records')
                df=pd.DataFrame(rows,columns=['station','init_utc','lead_h','source','fc_u','fc_v','fc_u100','fc_v100'])
                path.write_text(df.to_csv(index=False));meta.write_text(json.dumps({'source':source,'init':init.isoformat(),'url':url,'object_size':nbytes,'station_rows':len(df),'seconds':time.monotonic()-t}))
                print('OK',source,init.isoformat(),round(time.monotonic()-t,1),flush=True)
            except Exception as e:
                err=partdir/f'ERROR_{source}_{init.strftime("%Y%m%d%H")}.txt';err.write_text(traceback.format_exc())
                print('ERROR',source,init.isoformat(),str(e),flush=True)
        if init.day==1 and init.hour==0:print('MONTH_START',init.isoformat(),flush=True)
    print('FORECAST_DONE',len(inits),a.sources,flush=True)
if __name__=='__main__':main()
