#!/usr/bin/env python3
"""Frozen s2 official track chain. Reads a-deck only for forecasts; BEST only for verification."""
import sys,csv,gzip,io,json,math,statistics
from datetime import timedelta,timezone,datetime
from pathlib import Path
import numpy as np,xarray as xr
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'v1'))
import chain_a_v1 as v
old=v.old
OUT=Path(__file__).resolve().parent/'s2a'

def forecast_interp(pairs,t):
    lo=max((x for x in pairs if x[0]<=t),default=None,key=lambda x:x[0])
    hi=min((x for x in pairs if x[0]>=t),default=None,key=lambda x:x[0])
    if lo is None or hi is None or (hi[0]-lo[0]).total_seconds()>13*3600:return None
    w=(t-lo[0]).total_seconds()/max(1,(hi[0]-lo[0]).total_seconds())
    return [x+(y-x)*w for x,y in zip(lo[1],hi[1])]

def load_a(sid):
    url=f'https://ftp.nhc.noaa.gov/atcf/archive/{sid[-4:]}/a{sid}.dat.gz'
    raw=gzip.decompress(old.fetch(url)).decode(errors='replace')
    d={}
    for line in raw.splitlines():
        a=[x.strip() for x in line.split(',')]
        if len(a)<20 or a[4] not in ('OFCL','CARQ'):continue
        try:
            cycle=old.dt(a[2]+'00'); aid=a[4];lead=int(a[5]); key=(cycle,aid,lead)
            if key in d:continue
            d[key]={'t':cycle+timedelta(hours=lead),'lead':lead,'lat':old.atcf_coord(a[6]),'lon':old.atcf_coord(a[7]),'v':float(a[8]),'p':float(a[9]),'poci':float(a[17]),'rmw':float(a[19])}
        except (ValueError,IndexError):continue
    return d,url

def cycle_at(land,h):
    t=land-timedelta(hours=h)
    return t.replace(hour=12 if t.hour>=12 else 0,minute=0,second=0,microsecond=0)

def get_initial(a,cycle):
    q=a.get((cycle,'CARQ',0)) or a.get((cycle,'OFCL',0))
    if not q:return None,'no CARQ/OFCL 0'
    # Each field is CARQ first, OFCL 0 only if unavailable; no post-init or b-deck.
    o=a.get((cycle,'OFCL',0)) or {}
    rmw=q['rmw'] if q['rmw']>0 else o.get('rmw',0)
    poci=q['poci'] if q['poci']>0 else o.get('poci',0)
    p=q['p'] if q['p']>0 else o.get('p',0)
    if not 0<rmw<=200 or not 0<poci:return None,'no initial RMW/POCI'
    v0=q['v'] if q['v']>0 else o.get('v',0)
    if v0<=0:return None,'no initial Vmax'
    assumed=False
    if p<=0:p=poci-(v0/6.7)**(1/.644);assumed=True
    if not 0<p<poci:return None,'invalid initial pressure'
    return dict(rmw=rmw,poci=poci,p=p,v0=v0,seed_lat=q['lat'],seed_lon=q['lon'],p_assumed=assumed),None

def official(a,cycle,initial,start,end):
    rows=sorted((x for (c,aid,k),x in a.items() if c==cycle and aid=='OFCL' and k>=0 and x['v']>0),key=lambda x:x['t'])
    ans=[]
    for i in range(97):
        t=start+timedelta(minutes=15*i)
        z=forecast_interp([(x['t'],(x['lat'],x['lon'],x['v'])) for x in rows],t)
        if z is None:continue
        lat,lon,wind=z;p=initial['poci']-(initial['poci']-initial['p'])*(wind/initial['v0'])**(1/.644)
        if not 0<p<initial['poci']:continue
        ans.append((t,lat,lon,wind,p,initial['rmw'],initial['poci']))
    return ans,rows

def dataset(rows):
    if len(rows)<2:return None
    tm=np.array([np.datetime64(x[0].replace(tzinfo=None),'ns') for x in rows])
    return xr.Dataset(data_vars={
      'lat':('time',[x[1] for x in rows]),'lon':('time',[x[2] for x in rows]),
      'max_sustained_wind':('time',[x[3] for x in rows]),
      'central_pressure':('time',[x[4] for x in rows]),
      'radius_max_wind':('time',[x[5] for x in rows]),
      'environmental_pressure':('time',[x[6] for x in rows]),
      'time_step':('time',[.25]+[(rows[i][0]-rows[i-1][0]).total_seconds()/3600 for i in range(1,len(rows))])},coords={'time':tm},attrs={'max_sustained_wind_unit':'knots','central_pressure_unit':'mbar'})

def score(name,lead,rows,stations,observations,land,geometry):
    ds=dataset(rows)
    if ds is None:return [],None
    sustained,gust,exposure=v.predict(ds,stations,geometry)
    data=[]
    for j,st in enumerate(stations):
        key=(name,st['station']);obs=observations[key]
        ks=int(np.argmax(sustained[:,j]));kg=int(np.argmax(gust[:,j]))
        ps=float(sustained[ks,j]);pg=float(gust[kg,j]);t=rows[ks][0]
        data.append(dict(event=name,nominal_lead_h=lead,station=st['station'],reason=obs['reason'],
            obs_s_kt=obs['obs_s_kt'],obs_g_kt=obs['obs_g_kt'],pred_s_kt=round(ps,3),pred_g_kt=round(pg,3),
            model_peak_utc=t.isoformat(),err_s=(ps/float(obs['obs_s_kt'])-1 if obs['reason']=='eligible' and obs['obs_s_kt'] else None),
            err_g=(pg/float(obs['obs_g_kt'])-1 if obs['reason']=='eligible' and obs['obs_g_kt'] else None)))
    return data,ds

def main():
    assert not (OUT/'b_station_rows.csv').exists()
    events=list(csv.DictReader((BASE/'events_verified.csv').open()));observations={(r['event'],r['station']):r for r in csv.DictReader((BASE/'v1/run2/station_rows_v1.csv').open())}
    geo=v.get_land();allstations=[];allpaths=[];states=[]
    h=old.parse_hurdat()
    for ev in events:
        name=ev['name'];sid=ev['atcf_id'].lower();land=datetime.fromisoformat(ev['landfall_utc'])
        a,url=load_a(sid)
        ss={}
        for state in old.CANDIDATES[name][2].split(','):ss.update(old.stations(state,float(ev['lat']),float(ev['lon']),land))
        stations=[ss[k[1]] for k in observations if k[0]==name and k[1] in ss]
        if len(stations)!=sum(k[0]==name for k in observations):
            raise ValueError(f'{name} station metadata mismatch')
        best=h[name][1]
        for lead in (24,48,72):
            cycle=cycle_at(land,lead);start=land-timedelta(hours=12);end=land+timedelta(hours=12)
            initial,error=get_initial(a,cycle)
            status=dict(event=name,nominal_lead_h=lead,init_utc=cycle.isoformat(),actual_lead_h=(land-cycle).total_seconds()/3600,source=url,
                seed_carq=initial,error=error,n_stations=len(stations))
            if not error:
                rows,forecast=official(a,cycle,initial,start,end)
                status['nodes']=len(rows)
                if len(rows)>=2:
                    result,ds=score(name,lead,rows,stations,observations,land,geo);allstations+=result
                    errors=[]
                    for t,lat,lon,*_ in rows:
                        true=old.interp([(x['t'],(x['lat'],x['lon'])) for x in best],t,None)
                        if true:errors.append(old.km(lat,lon,*true))
                        allpaths.append(dict(event=name,nominal_lead_h=lead,init_utc=cycle.isoformat(),valid_utc=t.isoformat(),lat=lat,lon=lon,best_lat=true[0] if true else '',best_lon=true[1] if true else '',error_km=errors[-1] if true else ''))
                    at_land=forecast_interp([(x[0],(x[1],x[2])) for x in rows],land)
                    true_land=(float(ev['lat']),float(ev['lon']))
                    status['landfall_error_km']=old.km(*at_land,*true_land) if at_land else None
                    status['mean_12h_path_error_km']=statistics.mean(errors) if errors else None
                else:status['error']='forecast does not span window with two 15min nodes'
            states.append(status);print(name,lead,status.get('nodes'),status.get('error'),flush=True)
    for file,records in (('b_station_rows.csv',allstations),('b_paths.csv',allpaths)):
        with (OUT/file).open('x',newline='') as f:
            if records:w=csv.DictWriter(f,records[0].keys());w.writeheader();w.writerows(records)
    (OUT/'b_status.json').write_text(json.dumps(states,indent=2,default=str))
if __name__=='__main__':main()
