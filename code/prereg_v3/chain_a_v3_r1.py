#!/usr/bin/env python3
"""R23.3a v2 chain (a) BEST only. NEVER run before Lead freezes PREREG.

Standalone Colab CPU script: requires climada==6.1.0, numpy, xarray,
geopandas, shapely; stage Natural Earth ne_10m_land.zip and four CSVs.
Does not fetch observations, generate OFCL/Pangu, or execute paired (b)/(c).
"""
import argparse, csv, json, math, statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from rmw_adapter_v3 import Node, RadiusUnavailable, fit_series
UTC = timezone.utc
FIELDS = ('34','50','64')

def read(path):
    with open(path, newline='') as f: return list(csv.DictReader(f))

def when(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(UTC)

def selected_station(r, parallel=False):
    if r['homr_status'] != 'event_date_asos' or r['height_provenance'] != '2025_inventory_proxy_unverified_at_event': return False
    return r['parallel_eligible' if parallel else 'primary_eligible'] == 'yes_unverified_height'

def qc(hours, landfall, peak):
    """24 UTC hourly slots from floor(landfall-12h), [start,start+24h)."""
    start=(landfall-timedelta(hours=12)).replace(minute=0,second=0,microsecond=0)
    slots=[start+timedelta(hours=i) for i in range(24)]
    good={}; bad=0; duplicates=0
    for row in hours:
        try:
            if row.get('report_type') not in (None, '', '3'): continue
            t=when(row['time_utc']).replace(minute=0,second=0,microsecond=0)
            sk=float(row['sknt'])
            gust=float(row['gust_sknt']) if row.get('gust_sknt') not in ('',None) else None
            if sk<0 or (gust is not None and (gust<0 or gust<sk)):
                bad+=1;continue
            if t in good:
                duplicates+=1
                # Multiple scheduled reports in one bin: deterministic earliest valid report.
                if when(row['time_utc'])>=good[t][0]:continue
            good[t]=(when(row['time_utc']),sk)
        except (ValueError,KeyError,TypeError): bad+=1
    peak_hour=peak.replace(minute=0,second=0,microsecond=0)
    peak_slots=[peak_hour+timedelta(hours=i) for i in (-2,-1,0,1)]
    count=sum(t in good for t in slots)
    edge=any(t in good for t in slots[:2]) and any(t in good for t in slots[-2:])
    local=sum(t in good for t in peak_slots)>=3 and any(t in good for t in peak_slots[:2]) and any(t in good for t in peak_slots[2:])
    # If peak window is beyond the 24-hour base, extend both model and observation window.
    full=sorted(set(slots+peak_slots))
    extended=any(t not in slots for t in peak_slots)
    complete=count>=18 and edge and local and not bad
    obs=max((good[t][1] for t in full if t in good),default=None)
    return (obs if complete and obs and obs>0 else None,
            dict(coverage=count,edge=edge,peak_window=local,invalid_reports=bad,
                 duplicates=duplicates,extended=extended,censored=not complete,
                 first_valid=min(good).isoformat() if good else '',
                 last_valid=max(good).isoformat() if good else '',
                 obs_peak_lower_bound=obs))

def build_track(rows, hours=12, prior_weight=.25, bdeck=None):
    import numpy as np
    import xarray as xr
    nodes=[]; raw_times=[]
    for i,row in enumerate(rows):
        prev=rows[max(0,i-1)]; t=when(row['time_utc']); pt=when(prev['time_utc']); dt=(t-pt).total_seconds()/3600 if i else .25
        radii={}
        for k in (34,50,64):
            radii[k]=tuple(float(row.get(f'r{k}_{q}_nmi') or 0) for q in ('ne','se','sw','nw'))
        # v1 motion measured from successive BEST positions, max 30 kt as CLIMADA.
        lat0,lat1=math.radians(float(prev['lat'])),math.radians(float(row['lat']))
        dlat=lat1-lat0;dlon=math.radians(float(row['lon'])-float(prev['lon']))
        h=math.sin(dlat/2)**2+math.cos(lat0)*math.cos(lat1)*math.sin(dlon/2)**2
        distance=6371000*2*math.asin(min(1,math.sqrt(h)))
        speed=min(distance/(dt*3600),30*0.5144444444444445) if dt>0 else float('nan')
        node=Node(float(row['lat']),float(row['vmax_kt']),float(row['pc_hpa']),float(row['penv_hpa']),
                  float(prev['pc_hpa']),dt,speed,radii)
        nodes.append(node);raw_times.append(t)
    if len(nodes)<2:raise ValueError('fewer than two fitted track nodes')
    fits=fit_series(raw_times,nodes,hours=hours,prior_weight=prior_weight,bdeck=bdeck)
    if any((raw_times[i]-raw_times[i-1]).total_seconds()>7*3600 or raw_times[i]<=raw_times[i-1]
           for i in range(1,len(raw_times))):raise ValueError('BEST node gap >7h or unsorted')
    times=sorted(set([raw_times[0]+timedelta(minutes=15*i)
                     for i in range(int((raw_times[-1]-raw_times[0]).total_seconds()//900)+1)] +raw_times))
    def interp(field):
        vals=[f['rmw_nmi'] if field=='radius_max_wind' else float(r[field]) for r,f in zip(rows,fits)]
        stamps=[t.timestamp() for t in raw_times]
        return np.interp([t.timestamp() for t in times],stamps,vals)
    ds=xr.Dataset(data_vars={
        'lat':('time',interp('lat')),
        'lon':('time',interp('lon')),
        'max_sustained_wind':('time',interp('vmax_kt')),
        'central_pressure':('time',interp('pc_hpa')),
        'environmental_pressure':('time',interp('penv_hpa')),
        'radius_max_wind':('time',interp('radius_max_wind')),
        'time_step':('time',[.25]+[(times[i]-times[i-1]).total_seconds()/3600 for i in range(1,len(times))])},
        coords={'time':np.array([np.datetime64(t.replace(tzinfo=None),'ns') for t in times])},
        attrs={'max_sustained_wind_unit':'knots','central_pressure_unit':'mbar'})
    return ds,times,[dict(f,time_utc=r['time_utc']) for r,f in zip(rows,fits)]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('tracks','stations','observations','landfalls','land-zip','output'):p.add_argument('--'+key,required=True)
    p.add_argument('--lead-frozen',action='store_true')
    p.add_argument('--hours',type=int,default=12)
    p.add_argument('--prior-weight',type=float,default=.25)
    p.add_argument('--bdeck',action='store_true')
    args=p.parse_args()
    if not args.lead_frozen:raise SystemExit('NOT FROZEN: no model-observation pairing permitted')
    output=Path(args.output)
    if output.exists():raise FileExistsError(output)
    for key in ('tracks','stations','observations','landfalls','land_zip'):
        if not Path(getattr(args,key)).is_file():raise FileNotFoundError(getattr(args,key))
    from climada.hazard.trop_cyclone.trop_cyclone_windfields import tctrack_to_si,_compute_windfields,MODEL_VANG
    import numpy as np
    import geopandas as gpd
    from shapely import contains_xy,unary_union
    from shapely.geometry import box
    land=gpd.read_file('zip://'+str(Path(args.land_zip).resolve()))
    land=unary_union(land[land.geometry.intersects(box(-100,23,-75,37))].geometry.values)
    stations=read(args.stations); tracks=defaultdict(list); obs=defaultdict(list)
    for r in read(args.tracks): tracks[r['event']].append(r)
    for r in read(args.observations): obs[(r['event'],r['station'])].append(r)
    landfalls={r['event']:when(r['landfall_utc']) for r in read(args.landfalls)}
    events=sorted(landfalls)
    if len(events)<15:raise SystemExit('NO-GO: fewer than 15 intended events')
    cohort={e:[s for s in stations if s['event']==e and selected_station(s)] for e in events}
    parallel={e:[s for s in stations if s['event']==e and selected_station(s,True)] for e in events}
    if any(len(ss)<3 for ss in cohort.values()):raise SystemExit('NO-GO: primary station metadata <3 at some intended events')
    rows=[]; failures=[]
    for event in events:
        ss=list({s['station']:s for s in cohort[event]+parallel[event]}.values())
        try:
            ordered=sorted(tracks[event],key=lambda r:when(r['time_utc']))
            ds,times,fits=build_track(ordered,args.hours,args.prior_weight,
                [r.get('bdeck_rmw_nmi','') for r in ordered] if args.bdeck else None)
            coords=np.array([[float(s['lat']),float(s['lon'])] for s in ss])
            vectors,reachable=_compute_windfields(tctrack_to_si(ds),coords,MODEL_VANG['H08'],max_dist_eye_km=300)
            full=np.zeros((len(times),len(ss),2));full[:,reachable,:]=vectors
            speed=np.linalg.norm(full,axis=2)
            ux=np.divide(full[:,:,0],speed,out=np.zeros_like(speed),where=speed>0)
            uy=np.divide(full[:,:,1],speed,out=np.zeros_like(speed),where=speed>0)
            lon=coords[:,1][None,:];lat=coords[:,0][None,:]
            votes=[]
            for dist in (2,5,10):
                qlon=np.broadcast_to(lon,ux.shape)-dist*ux/(111.2*np.cos(np.radians(lat)))
                qlat=np.broadcast_to(lat,uy.shape)-dist*uy/111.2
                votes.append(contains_xy(land,qlon,qlat))
            on_land=np.sum(votes,axis=0)>=2
            f_land=(math.log(10/.03)/math.log(500/.03))/(math.log(10/.0013)/math.log(500/.0013))
            sustained=speed*np.where(on_land,f_land,1.0)*.97/.5144444444444445
            for j,s in enumerate(ss):
                mask=[k for k,t in enumerate(times) if abs((t-landfalls[event]).total_seconds())<=12*3600]
                if not mask:raise ValueError('no BEST node inside landing window')
                ix=max(mask,key=lambda k:sustained[k,j]);tstar=times[ix]
                measured,qc_flags=qc(obs[(event,s['station'])],landfalls[event],tstar)
                z=float(s['inventory_height_m']); z0=.03 if on_land[ix,j] else .0013
                factor=math.log(10/z0)/math.log(z/z0)
                observed10=measured*factor if measured else None
                pred=float(sustained[ix,j])
                rows.append(dict(event=event,station=s['station'],pool='primary' if selected_station(s) else 'parallel_only',height_m=z,height_unverified='yes',
                    z0_m=z0,height_factor=factor,tstar_utc=tstar.isoformat(),pred_10m_sknt=pred,
                    observed_10m_sknt=observed10,error=pred/observed10-1 if observed10 else '',
                    rmw_fits=json.dumps(fits),qc=json.dumps(qc_flags)))
        except (ValueError,KeyError,RadiusUnavailable) as exc:
            failures.append(dict(event=event,reason=str(exc)))
    # A partial event is retained only as a diagnostic; never pass the 15 x 3 gate.
    valid=Counter(r['event'] for r in rows if r['pool']=='primary' and r['error'] != '')
    verdict='evaluable' if not failures and all(valid[e]>=3 for e in events) else 'not_evaluable'
    if not rows:raise ValueError('no rows; '+json.dumps(failures))
    with output.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    errors=[float(r['error']) for r in rows if r['error']!='']
    print(json.dumps(dict(verdict=verdict,event_count=len(events),per_event=valid,
          failures=failures,median_bias=statistics.median(errors) if verdict=='evaluable' else None,
          candidate_station_errors_not_for_gate=len(errors)),default=dict))
if __name__=='__main__':main()
