#!/usr/bin/env python3
"""H2 eleven-event extension; original two-event artifacts remain untouched."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import io, json, math, importlib.util, sys
from pathlib import Path
from datetime import timedelta
import numpy as np, pandas as pd, requests, xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'vendor'))
import chain_a_v1 as b
import run_h2 as h2
old=b.old
EVENTS=['DELTA','ZETA','IDA','NICHOLAS','IAN','NICOLE','IDALIA','DEBBY','HELENE','MILTON','BERYL']
STATES={'DELTA':'LA,TX','ZETA':'LA,MS,AL','IDA':'LA,MS','NICHOLAS':'TX,LA','IAN':'FL','NICOLE':'FL','IDALIA':'FL,GA','DEBBY':'FL,GA','HELENE':'FL,GA','MILTON':'FL','BERYL':'TX'}
METHODS=h2.METHODS

def read_or_make(path, maker):
    if path.exists(): return pd.read_csv(path)
    df=maker(); df.to_csv(path,index=False); return df

def get_grid(name,hurdat,land):
    # Reuse already downloaded Beryl/Nicholas hourly records and unchanged v1 predictions.
    gridpath=R/f'grid_{name.lower()}_h2.csv.gz'
    if gridpath.exists():
        print(name,'cached grid',flush=True); return pd.read_csv(gridpath,parse_dates=['hour'])
    dest=R/f'grid_{name.lower()}_expanded.csv.gz'
    if dest.exists():
        print(name,'cached expanded grid',flush=True); return pd.read_csv(dest,parse_dates=['hour'])
    sid,rows=hurdat[name]; t=old.dt(old.CANDIDATES[name][1]); start=t-timedelta(hours=12); end=t+timedelta(hours=12)
    track,error=b.build_track(rows,old.bdeck(sid),start,end)
    if error: raise RuntimeError(name+': '+error)
    hours=pd.date_range(pd.Timestamp(start).ceil('h'),pd.Timestamp(end).floor('h'),freq='h',tz='UTC')
    tt=pd.to_datetime(track.time.values,utc=True)
    stations={}
    for state in STATES[name].split(','):
        features=json.loads(old.fetch(old.GEO.format(state=state)))['features']
        for f in features:
            props=f['properties']; lon,lat=f['geometry']['coordinates'][:2]
            if min(old.km(lat,lon,float(a),float(c)) for a,c in zip(track.lat.values,track.lon.values))>300:continue
            if not (props.get('archive_begin') or '1900-01-01')[:10]<=t.date().isoformat()<=(props.get('archive_end') or '2100-01-01')[:10]:continue
            key=state+':'+f['id']
            stations[key]={'station':f['id'],'state':state,'lat':lat,'lon':lon}
    sites=sorted(stations.values(),key=lambda s:(s['state'],s['station']))
    print(name,'stations',len(sites),'hours',len(hours),flush=True)
    if not sites: raise RuntimeError('No stations for '+name)
    pd.DataFrame(sites).to_csv(R/f'stations_{name.lower()}_expanded.csv',index=False)
    wind,gust,_=b.predict(track,sites,land)
    wh=np.array([np.interp(hours.asi8,tt.asi8,wind[:,j]) for j in range(len(sites))]).T*old.KNOT
    gh=np.array([np.interp(hours.asi8,tt.asi8,gust[:,j]) for j in range(len(sites))]).T*old.KNOT
    la=np.interp(hours.asi8,tt.asi8,track.lat.values);lo=np.interp(hours.asi8,tt.asi8,track.lon.values)
    rmw=np.interp(hours.asi8,tt.asi8,track.radius_max_wind.values)*1.852
    records=[]
    for k,hr in enumerate(hours):
        for j,s in enumerate(sites):
            d=old.km(s['lat'],s['lon'],la[k],lo[k]);records.append(dict(event=name,station=s['state']+':'+s['station'],hour=hr,lat=s['lat'],lon=s['lon'],distance_km=d,rmw_ratio=d/rmw[k],holland=wh[k,j],holland_gust=gh[k,j]))
    grid=pd.DataFrame(records)
    def fetch_obs():
        parts=[];urls=[]
        for state in STATES[name].split(','):
            ss=[s['station'] for s in sites if s['state']==state]
            for i in range(0,len(ss),35):
                params=dict(station=','.join(ss[i:i+35]),sts=(start-timedelta(hours=1)).strftime('%Y-%m-%dT%H:%MZ'),ets=(end+timedelta(hours=1)).strftime('%Y-%m-%dT%H:%MZ'),tz='UTC',format='onlycomma',data='sknt,gust,metar',report_type='3,4')
                url='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py'
                resp=requests.get(url,params=params,timeout=240);resp.raise_for_status()
                table=pd.read_csv(io.StringIO(resp.text),comment='#',low_memory=False)
                if not {'station','valid','sknt','gust'}.issubset(table): raise RuntimeError(resp.url+' '+resp.text[:200])
                table['station']=state+':'+table.station.astype(str);parts.append(table);urls.append(resp.url)
                print(name,state,i,'IEM bytes',len(resp.content),flush=True)
        (R/f'iem_urls_{name.lower()}_expanded.json').write_text(json.dumps(urls,indent=2))
        return pd.concat(parts,ignore_index=True)
    obs=read_or_make(R/f'metar_{name.lower()}_expanded.csv.gz',fetch_obs)
    obs.valid=pd.to_datetime(obs.valid,utc=True,errors='coerce');obs['hour']=(obs.valid+pd.Timedelta(minutes=30)).dt.floor('h')
    obs=obs[obs.hour.isin(hours)].copy();obs['delta']=(obs.valid-obs.hour).abs()
    obs=obs.sort_values(['station','hour','delta','valid']).drop_duplicates(['station','hour'])
    for field,upper in [('sknt',120),('gust',150)]:
        obs[field]=pd.to_numeric(obs[field],errors='coerce');obs.loc[~obs[field].between(0,upper),field]=np.nan
    obs.loc[obs.gust<obs.sknt,'gust']=np.nan
    obs['obs']=obs.sknt*old.KNOT;obs['obs_gust']=obs.gust*old.KNOT
    def fetch_era():
        uri='gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
        ds=xr.open_zarr(uri,chunks=None,storage_options={'token':'anon'})[['10m_u_component_of_wind','10m_v_component_of_wind']]
        loc={'latitude':xr.DataArray([s['lat'] for s in sites],dims='station'),'longitude':xr.DataArray([s['lon']%360 for s in sites],dims='station')}
        a=ds.sel(time=slice(hours[0].tz_localize(None).isoformat(),hours[-1].tz_localize(None).isoformat())).interp(**loc).load()
        if a.sizes['time']!=len(hours):raise RuntimeError('ERA hour mismatch '+name)
        speed=np.hypot(a['10m_u_component_of_wind'].values,a['10m_v_component_of_wind'].values)
        print(name,'ERA loaded',speed.shape,flush=True)
        return pd.DataFrame([{'station':s['state']+':'+s['station'],'hour':hr.isoformat(),'era':float(speed[k,j])} for k,hr in enumerate(hours) for j,s in enumerate(sites)])
    era=read_or_make(R/f'era_{name.lower()}_expanded.csv',fetch_era);era.hour=pd.to_datetime(era.hour,utc=True)
    grid=grid.merge(obs[['station','hour','obs','obs_gust']],on=['station','hour'],how='left',validate='one_to_one').merge(era,on=['station','hour'],validate='one_to_one')
    grid.to_csv(dest,index=False,compression='gzip');return grid

def score(x,y):return h2.score(x,y)
def calc():
    hurdat=old.parse_hurdat();land=b.get_land(); grids=[];preds=[];missing=[];coverage={}
    for name in EVENTS:
        g=get_grid(name,hurdat,land);grids.append(g)
        for sid,s in g.groupby('station'):
            expected=s.hour.nunique();valid=int(s.obs.notna().sum());peak_t=s.loc[s.holland.idxmax(),'hour']
            bracket=bool(((s.hour-peak_t).abs()<=pd.Timedelta(hours=2)).mul(s.obs.notna()).any())
            eligible=valid>=math.ceil(.75*expected) and bracket
            coverage[(name,sid)]=eligible
            if not eligible:missing.append({'event':name,'station':sid,'valid_hours':valid,'expected_hours':expected,'model_peak_utc':peak_t.isoformat(),'near_model_peak':bracket,'reason':'insufficient_hours' if valid<math.ceil(.75*expected) else 'no_report_near_model_peak'})
        print(name,'eligible',sum(coverage[(name,s)] for s in g.station.unique()),'of',g.station.nunique(),flush=True)
        # Save event-wise predictions to survive interrupted runs.
        pp=R/f'predictions_{name.lower()}_expanded.csv.gz'
        if pp.exists(): p=pd.read_csv(pp,parse_dates=['hour'])
        else:
            p=h2.predict(g);p.to_csv(pp,index=False,compression='gzip')
        if len(p):p['eligible']=[coverage[(e,s)] for e,s in zip(p.event,p.station)];preds.append(p)
    p=pd.concat(preds,ignore_index=True)
    pd.DataFrame(missing).to_csv(R/'missing_stations_h2_expanded.csv',index=False)
    p.to_csv(R/'predictions_h2_expanded.csv.gz',index=False,compression='gzip')
    peakrows=[]
    for (event,sid),s in p[p.eligible].groupby(['event','station']):
        row={'event':event,'station':sid,'obs':float(s.obs.max()),'obs_gust':float(s.obs_gust.max()),'rmw_ratio':float(s.loc[s.obs.idxmax(),'rmw_ratio'])}
        for m in METHODS:row[m]=float(s[m].max())
        for m in ['gust_idw','gust_ok','gust_holland','gust_holland_resok']:
            row[m]=float(s[m].max()) if m in s and s[m].notna().any() else np.nan
        peakrows.append(row)
    peaks=pd.DataFrame(peakrows);peaks.to_csv(R/'peaks_h2_expanded.csv',index=False)
    metrics={}
    evaluable=[e for e in EVENTS if len(peaks[peaks.event==e])>=8]
    for event in EVENTS+['COMBINED']:
        if event=='COMBINED':
            official=[e for e in evaluable if e!='BERYL']
            pp=peaks[peaks.event.isin(official)];hh=p[p.eligible & p.event.isin(official)]
        else:pp=peaks[peaks.event==event];hh=p[(p.eligible)&(p.event==event)]
        by={m:{'peak':score(pp[m],pp.obs),'hourly':score(hh[m],hh.obs)} for m in METHODS}
        by['gust']={m:score(pp[m],pp.obs_gust) for m in ['gust_idw','gust_ok','gust_holland','gust_holland_resok']}
        eligible=len(pp)>=8
        base=min(['idw','ok'],key=lambda m:by[m]['peak']['rmse']) if len(pp) else None
        fusion=min(['era_resok','holland_resok'],key=lambda m:by[m]['peak']['rmse']) if len(pp) else None
        gain=(1-by[fusion]['peak']['rmse']/by[base]['peak']['rmse']) if eligible and by[base]['peak']['rmse'] else None
        wins=int(((pp[fusion]-pp.obs).abs()<(pp[base]-pp.obs).abs()).sum()) if eligible else None
        groups={}
        if eligible:
            for label,mask in {'<1R':pp.rmw_ratio<1,'1-3R':(pp.rmw_ratio>=1)&(pp.rmw_ratio<=3),'>3R':pp.rmw_ratio>3}.items():
                groups[label]={'n':int(mask.sum()),base:score(pp.loc[mask,base],pp.loc[mask,'obs']),fusion:score(pp.loc[mask,fusion],pp.loc[mask,'obs'])}
        metrics[event]={'stations':len(pp),'hourly_records':len(hh),'evaluable':eligible,'methods':by,'baseline':base,'best_fusion':fusion,'gain':gain,'station_wins':wins,'distance_groups':groups,'not_eligible':sum(q['event']==event for q in missing) if event!='COMBINED' else sum(q['event'] in official for q in missing)}
    payload={'metadata':{'events':EVENTS,'evaluable_events':evaluable,'combined_excludes_beryl':True,'original_h2_preserved':True,'peak_rule':'maximum on common observed hours','windfield':'unmodified chain_a_v1.py copied into h2; import path only changed'},'metrics':metrics}
    (R/'metrics_h2_expanded.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False))
    if len(peaks):
        fig,ax=plt.subplots(figsize=(7,7));
        for e,s in peaks.groupby('event'):ax.scatter(s.obs,s.holland_resok,alpha=.65,label=f'{e} ({len(s)})',s=22)
        mx=max(peaks.obs.max(),peaks.holland_resok.max())*1.1;ax.plot([0,mx],[0,mx],'k--');ax.set(xlim=(0,mx),ylim=(0,mx),xlabel='Observed peak sustained METAR wind (m/s)',ylabel='H08 + residual OK predicted peak (m/s)',title='IEM METAR / NHC HURDAT2 & ATCF / CLIMADA H08');ax.legend(fontsize=7,ncol=2);fig.tight_layout();fig.savefig(R/'peak_scatter_h2_expanded.png',dpi=160)
    print(json.dumps({e:{k:v for k,v in a.items() if k in ('stations','evaluable','baseline','best_fusion','gain','station_wins','not_eligible')} for e,a in metrics.items()},indent=2),flush=True)
if __name__=='__main__':calc()
