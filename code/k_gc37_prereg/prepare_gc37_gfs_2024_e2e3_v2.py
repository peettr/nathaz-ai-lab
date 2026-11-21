#!/usr/bin/env python3
"""Prepare E2/E3 2024 GFS L37 input on Colab, preserving native 31-layer q."""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import time
import urllib.request
import numpy as np
import xarray as xr
import pygrib
from apcp_identical_v2 import select_identical_apcp

LEVELS=np.array([1,2,3,5,7,10,20,30,50,70,100,125,150,175,200,225,250,300,350,400,450,500,550,600,650,700,750,775,800,825,850,875,900,925,950,975,1000],dtype=np.int32)
MID={125,175,225,775,825,875}
BASE='https://osdf-director.osg-htc.org/ncar/gdex/'
HERE=pathlib.Path(__file__).resolve().parent

def url(dataset,t,forecast=0):
    stem='gfs.0p25b' if dataset=='d084003' else 'gfs.0p25'
    return f'{BASE}{dataset}/2024/{t:%Y%m%d}/{stem}.{t:%Y%m%d%H}.f{forecast:03d}.grib2'

def download(u,dest):
    if not dest.exists():
        tmp=dest.with_suffix('.partial')
        if tmp.exists():raise FileExistsError(tmp)
        started=time.monotonic()
        with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=200) as response,tmp.open('xb') as out:
            if response.status!=200:raise RuntimeError((u,response.status))
            while chunk:=response.read(4*1024*1024):out.write(chunk)
        tmp.rename(dest)
        print('download',u,dest.stat().st_size,'seconds',round(time.monotonic()-started,2),flush=True)
    with dest.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    return {'url':u,'bytes':dest.stat().st_size,'sha256':digest}

def rec(grb,short,level=None,typ=None):
    query={'shortName':short}
    if level is not None:query.update(level=int(level),typeOfLevel=typ or 'isobaricInhPa')
    matches=grb.select(**query)
    if len(matches)!=1:raise ValueError(('missing_or_duplicate_native',short,level,typ,len(matches)))
    return matches[0]

def val(msg):
    data=msg.values
    if np.ma.isMaskedArray(data):data=data.filled(np.nan)
    data=np.asarray(data,dtype='float32')
    if data.shape!=(721,1440):raise ValueError(('grib_shape',msg.shortName,data.shape))
    return data[::-1,:].copy()

def bolton_q(t,r,p_hpa):
    """Bolton es=611.2 exp(17.67*(T-273.15)/(T-29.65)) Pa, q=.622e/(p-.378e)."""
    es=611.2*np.exp(17.67*(t-273.15)/(t-29.65))
    e=np.clip(r/100*es,0,p_hpa*100*.99)
    return np.asarray(.622*e/(p_hpa*100-.378*e),dtype='float32')

def state(t,raw):
    gm=pygrib.open(str(raw[f'main_{t:%Y%m%d%H}']))
    ga=pygrib.open(str(raw[f'aux_{t:%Y%m%d%H}']))
    fieldmap={'geopotential':'gh','temperature':'t','u_component_of_wind':'u','v_component_of_wind':'v','specific_humidity':'q','vertical_velocity':'w'}
    fields={};origins={}
    try:
        for name,short in fieldmap.items():
            arr=np.empty((len(LEVELS),721,1440),dtype='float32');origins[name]={}
            for ix,p in enumerate(LEVELS):
                if short=='w' and p<100:
                    arr[ix]=0;origins[name][str(p)]='approved_upper_w_zero';continue
                source=ga if p in MID else gm
                if short=='q' and p in MID:
                    # d084003 has RH but no native q. Convert RH and T at the SAME level.
                    temperature=val(rec(ga,'t',p));rh=val(rec(ga,'r',p))
                    arr[ix]=bolton_q(temperature,rh,int(p))
                    origins[name][str(p)]='d084003 RH/T Bolton'
                else:
                    arr[ix]=val(rec(source,short,p))
                    origins[name][str(p)]='d084003' if source is ga else 'd084001'
            if name=='geopotential':arr*=np.float32(9.80665)
            if not np.isfinite(arr).all():raise ValueError(('nonfinite_aloft',t.isoformat(),name,int(np.count_nonzero(~np.isfinite(arr)))))
            fields[name]=arr
        surface={'2m_temperature':val(rec(gm,'2t')),'10m_u_component_of_wind':val(rec(gm,'10u')),'10m_v_component_of_wind':val(rec(gm,'10v')),'mean_sea_level_pressure':val(rec(gm,'prmsl'))}
        static={'geopotential_at_surface':val(rec(gm,'orog'))*np.float32(9.80665),'land_sea_mask':val(rec(gm,'lsm'))}
        for name,a in {**surface,**static}.items():
            if not np.isfinite(a).all():raise ValueError(('nonfinite_surface',t.isoformat(),name))
        return fields,surface,static,origins
    finally:gm.close();ga.close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cycle',required=True);parser.add_argument('--root',required=True);args=parser.parse_args()
    root=pathlib.Path(args.root);root.mkdir(parents=True,exist_ok=True)
    t0=dt.datetime.strptime(args.cycle,'%Y%m%d%H');times=[t0-dt.timedelta(hours=6),t0]
    wanted={}
    for t in times:
        for ds,prefix in (('d084001','main'),('d084003','aux')):wanted[f'{prefix}_{t:%Y%m%d%H}']=url(ds,t)
        wanted[f'precip_{t:%Y%m%d%H}']=url('d084001',t-dt.timedelta(hours=6),6)
    raw={};provenance={}
    for key,u in wanted.items():
        path=root/'raw'/u.rsplit('/',1)[-1];path.parent.mkdir(parents=True,exist_ok=True)
        provenance[key]=download(u,path);raw[key]=path
    states=[];surfaces=[];origins={};static=None
    for t in times:
        fields,surface,static,origin=state(t,raw)
        g=pygrib.open(str(raw[f'precip_{t:%Y%m%d%H}']))
        try:
            matches=[m for m in g.select(shortName='tp',typeOfLevel='surface') if str(m.stepRange) in ('0-6','6')]
            selected,dedup=select_identical_apcp(matches)
            print('APCP_DEDUP',t.isoformat(),json.dumps(dedup),flush=True)
            surface['total_precipitation_6hr']=val(selected)/np.float32(1000)
            if not np.isfinite(surface['total_precipitation_6hr']).all():raise ValueError(('apcp_nonfinite',t.isoformat()))
        finally:g.close()
        states.append(fields);surfaces.append(surface);origins[t.isoformat()]=origin
    coords={'batch':np.array([0]),'time':np.array([np.timedelta64(-6,'h'),np.timedelta64(0,'h')]),'level':LEVELS,'lat':np.arange(-90,90.0001,.25,dtype='float32'),'lon':np.arange(0,360,.25,dtype='float32')}
    data={name:(('batch','time','level','lat','lon'),np.stack([s[name] for s in states])[None,...]) for name in states[0]}
    data.update({name:(('batch','time','lat','lon'),np.stack([s[name] for s in surfaces])[None,...]) for name in surfaces[0]})
    data.update({name:(('lat','lon'),a) for name,a in static.items()})
    ds=xr.Dataset(data,coords=coords).assign_coords(datetime=(('batch','time'),np.array([[np.datetime64(t,'ns') for t in times]])))
    dest=root/f'input_{args.cycle}_zero.nc'
    if dest.exists():raise FileExistsError(dest)
    ds.to_netcdf(dest,engine='netcdf4',encoding={k:{'zlib':True,'complevel':1} for k in data});ds.close()
    with dest.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    report={'cycle':args.cycle,'case':'zero','input_sha256':sha,'sources':provenance,'origins':origins,'model_levels_hpa':LEVELS.tolist(),'humidity_formula':'Bolton es=611.2 exp(17.67*(T-273.15)/(T-29.65)) Pa; e=RH/100 es clipped [0,.99p]; q=.622 e/(p-.378 e); native q from d084001 at non-middle 31 layers.'}
    (root/f'input_{args.cycle}_zero.json').write_text(json.dumps(report,indent=2))
    print('INPUT_READY',dest,sha,flush=True)
if __name__=='__main__':main()
