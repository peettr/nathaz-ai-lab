#!/usr/bin/env python3
"""Frozen v1, see PREREG_v1.md. CLIMADA v6.1.0 H08, directional exposure."""
import argparse, csv, importlib.util, json, math, statistics, sys, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path
import numpy as np
import xarray as xr
import geopandas as gpd
from shapely import contains_xy, unary_union
from shapely.geometry import box
from climada.hazard.trop_cyclone.trop_cyclone_windfields import tctrack_to_si, _compute_windfields, MODEL_VANG

HERE=Path(__file__).resolve().parent
OUT=HERE
spec=importlib.util.spec_from_file_location('old_chain_a', HERE/'chain_a.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
F_LAND=(math.log(10/.03)/math.log(500/.03))/(math.log(10/.0013)/math.log(500/.0013))


def get_land():
    g=gpd.read_file('zip://'+str(HERE/'ne_10m_land.zip'))
    g=g[g.geometry.intersects(box(-100,23,-75,37))]
    return unary_union(g.geometry.values)


def build_track(rows, rmw, start, end):
    times=[start-timedelta(minutes=15)+timedelta(minutes=15*k) for k in range(98)]
    out=[]
    for t in times:
        a=old.interp([(v['t'],(v['lat'],v['lon'],v['v'],v['p'])) for v in rows],t,None)
        b=old.interp(rmw,t,None)
        if not a or not b or b[0]<=0 or b[1]<=a[3]:continue
        out.append((t,*a,*b))
    if len(out)<2:return None,'fewer than two usable 15-min track nodes'
    tm=np.array([np.datetime64(x[0].replace(tzinfo=None),'ns') for x in out])
    ds=xr.Dataset(data_vars={
      'lat':('time',[x[1] for x in out]),'lon':('time',[x[2] for x in out]),
      'max_sustained_wind':('time',[x[3] for x in out]),
      'central_pressure':('time',[x[4] for x in out]),
      'radius_max_wind':('time',[x[5] for x in out]),
      'environmental_pressure':('time',[x[6] for x in out]),
      'time_step':('time',[.25]+[(out[i][0]-out[i-1][0]).total_seconds()/3600 for i in range(1,len(out))])},coords={'time':tm},
      attrs={'max_sustained_wind_unit':'knots','central_pressure_unit':'mbar'})
    return ds,None


def predict(track, stations, land):
    arr=np.array([(s['lat'],s['lon']) for s in stations])
    si=tctrack_to_si(track)
    vectors,reachable=_compute_windfields(si,arr,MODEL_VANG['H08'],max_dist_eye_km=300)
    full=np.zeros((len(track.time),len(stations),2));full[:,reachable,:]=vectors
    # CLIMADA vector components are east,north; upstream follows negative wind vector.
    speed=np.linalg.norm(full,axis=2)
    lon=arr[:,1][None,:];lat=arr[:,0][None,:]
    ux=np.divide(full[:,:,0],speed,out=np.zeros_like(speed),where=speed>0)
    uy=np.divide(full[:,:,1],speed,out=np.zeros_like(speed),where=speed>0)
    votes=[]
    for dist in (2,5,10):
        qlon=np.broadcast_to(lon,ux.shape)-dist*ux/(111.2*np.cos(np.radians(lat)))
        qlat=np.broadcast_to(lat,uy.shape)-dist*uy/111.2
        votes.append(contains_xy(land,qlon,qlat))
    on_land=np.sum(votes,axis=0)>=2
    exposure=np.where(on_land,F_LAND,1.0)
    sustained=speed*exposure*.97/old.KNOT
    gust=speed*exposure*np.where(on_land,1.30,1.20)/old.KNOT
    return sustained,gust,on_land


def station_observation(st,tstar,landtime, pred_s,pred_g,on_land):
    start=tstar-timedelta(hours=6);end=tstar+timedelta(hours=6)
    data,error,url=old.obs(st,start,end)
    d={}
    for t,s,g in data:
        if start<=t<end:d[t]=(s,g)
    bad=any(s is not None and g is not None and s>=0 and g>=0 and g<s for s,g in d.values())
    valid=[(t,s) for t,(s,g) in d.items() if s is not None and s>=0]
    gust=[g for t,(s,g) in d.items() if g is not None and g>=0]
    if valid and gust and max(gust)<max(v for _,v in valid):bad=True
    truncated=(len(valid)<648 or not valid or min(t for t,_ in valid)>tstar or max(t for t,_ in valid)<tstar)
    reason='request_error' if error else 'qc' if bad else 'truncated' if truncated else 'eligible'
    obs_s=max((s for _,s in valid),default=None);obs_g=max(gust,default=None)
    good=reason=='eligible'
    return dict(event=landtime,station=st['station'],state=st['state'],distance_km=round(st['distance_km'],2),
        model_peak_utc=tstar.isoformat(),first_valid_utc=min((t for t,_ in valid),default=None),
        last_valid_utc=max((t for t,_ in valid),default=None),sknt_valid=len(valid),gust_valid=len(gust),
        obs_s_kt=obs_s,obs_g_kt=obs_g,pred_s_kt=round(pred_s,3),pred_g_kt=round(pred_g,3),
        pred_peak_land=bool(on_land),reason=reason,fetch_error=error or '',obs_url=url,
        err_s=(pred_s/obs_s-1) if good and obs_s and pred_s>0 else None,
        err_g=(pred_g/obs_g-1) if good and obs_g and pred_g>0 else None)


def main():
    global OUT
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args()
    OUT=Path(args.output);OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'summary_v1.json').exists():raise FileExistsError(OUT/'summary_v1.json')
    land=get_land();h=old.parse_hurdat();allrows=[]
    for name,(year,landing,states) in old.CANDIDATES.items():
        sid,rawtrack=h[name];t=old.dt(landing)
        l=next(x for x in rawtrack if x['t']==t and x['record']=='L')
        stations={}
        for state in states.split(','):stations.update(old.stations(state,l['lat'],l['lon'],t))
        rmw=old.bdeck(sid)
        start,end=t-timedelta(hours=12),t+timedelta(hours=12)
        track,error=build_track(rawtrack,rmw,start,end)
        if error:
            print(name,error,flush=True);continue
        ss=list(stations.values())
        if not ss:print(name,'no stations',flush=True);continue
        sustained,gust,on_land=predict(track,ss,land)
        # Track array starts 15 minutes before observation window; first position is zero.
        times=[old.datetime.fromisoformat(np.datetime_as_string(x,unit='s')).replace(tzinfo=old.timezone.utc) for x in track.time.values]
        tasks=[]
        with ThreadPoolExecutor(max_workers=8) as ex:
            for j,st in enumerate(ss):
                k=int(np.argmax(sustained[:,j]));kg=int(np.argmax(gust[:,j]))
                tasks.append(ex.submit(station_observation,st,times[k],name,float(sustained[k,j]),float(gust[kg,j]),on_land[k,j]))
            for fut in as_completed(tasks):allrows.append(fut.result())
        print(name,len(ss),'eligible',sum(x['event']==name and x['reason']=='eligible' for x in allrows),flush=True)
        # Append one completed event at a time, preserving progress across network failures.
        rows=[x for x in allrows if x['event']==name]
        with (OUT/f'{name.lower()}_stations.csv').open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    if not allrows:raise RuntimeError('No event observations completed')
    with (OUT/'station_rows_v1.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=allrows[0].keys());w.writeheader();w.writerows(sorted(allrows,key=lambda x:(x['event'],x['station'])))
    summary={}
    for metric in ('s','g'):
        errors=[x['err_'+metric] for x in allrows if x['err_'+metric] is not None]
        summary[metric]={'n':len(errors),'median_abs_error':statistics.median(map(abs,errors)) if errors else None,
                         'median_bias':statistics.median(errors) if errors else None}
    summary['stations']=len(allrows)
    summary['truncated']=sum(x['reason']=='truncated' for x in allrows)
    summary['qc']=sum(x['reason']=='qc' for x in allrows)
    summary['request_error']=sum(x['reason']=='request_error' for x in allrows)
    summary['by_event']={name:{'candidate':sum(x['event']==name for x in allrows),
        'eligible':sum(x['event']==name and x['reason']=='eligible' for x in allrows),
        'truncated':sum(x['event']==name and x['reason']=='truncated' for x in allrows)} for name in old.CANDIDATES}
    (OUT/'summary_v1.json').write_text(json.dumps(summary,indent=2))
    print('SUMMARY',json.dumps(summary),flush=True)

if __name__=='__main__':main()
