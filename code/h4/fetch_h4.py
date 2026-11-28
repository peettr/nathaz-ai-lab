import io,json,math,collections
from pathlib import Path
import pandas as pd,numpy as np,requests,xarray as xr
from PIL import Image
R=Path(__file__).resolve().parent
cfg=json.loads((R/'events_h4.json').read_text());feat=requests.get('https://mesonet.agron.iastate.edu/geojson/network/ASOS1MIN.geojson',timeout=90).json()['features']
sites=[]
for f in feat:
    lon,lat=f['geometry']['coordinates'][:2];p=f['properties']
    if 31.5<=lat<=34 and -98.5<=lon<=-95.5:sites.append(dict(station=f['id'],lat=lat,lon=lon,name=p.get('sname',''),elevation=p.get('elevation'),begin=p.get('archive_begin','1900') or '1900',end=p.get('archive_end','2100') or '2100'))
meta=pd.DataFrame(sites);meta.to_csv(R/'stations_h4.csv',index=False)
uri='gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3';ds=None
for day in cfg['chosen_utc_dates']:
    tag=day.replace('-','');rawpath=R/f'raw_minute_{tag}_h4.csv.gz';gridpath=R/f'grid_{tag}_h4.csv.gz'
    if gridpath.exists():print('CACHED',day,flush=True);continue
    s=meta[(meta.begin<=day)&(meta.end>=day)].copy()
    start=pd.Timestamp(day,tz='UTC')-pd.Timedelta(hours=6);end=start+pd.Timedelta(hours=36)
    p=dict(station=','.join(s.station),tz='UTC',vars='sknt,gust_sknt',sample='1min',what='view',delim='comma',sts=start.strftime('%Y-%m-%dT%H:%MZ'),ets=end.strftime('%Y-%m-%dT%H:%MZ'))
    # explicit calendar parameters are the documented, tested API path
    for k,t in [(1,start),(2,end)]:
        for key,val in [('year',t.year),('month',t.month),('day',t.day),('hour',t.hour),('minute',t.minute)]:p[key+str(k)]=val
    resp=requests.get('https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py',params=p,timeout=240);resp.raise_for_status()
    raw=pd.read_csv(io.StringIO(resp.text),comment='#');assert {'station','valid(UTC)','sknt','gust_sknt'}<=set(raw.columns),(day,raw.columns,resp.text[:300]);raw.to_csv(rawpath,index=False,compression='gzip');(R/f'iem_minute_url_{tag}_h4.txt').write_text(resp.url+'\n')
    raw['valid']=pd.to_datetime(raw['valid(UTC)'],utc=True,errors='coerce');raw=raw[raw.station.isin(s.station)&raw.valid.notna()].copy()
    for key,hi in [('sknt',120),('gust_sknt',150)]:raw[key]=pd.to_numeric(raw[key],errors='coerce');raw.loc[~raw[key].between(0,hi),key]=np.nan
    raw.loc[raw.gust_sknt<raw.sknt,'gust_sknt']=np.nan
    peak=raw.groupby('valid').gust_sknt.max().idxmax();hours=pd.date_range(peak-pd.Timedelta(hours=3),peak+pd.Timedelta(hours=3),freq='min',tz='UTC');center=peak.floor('h')
    raw=raw[raw.valid.isin(hours)].sort_values('valid').drop_duplicates(['station','valid']);raw['obs']=raw.sknt*.514444;raw['gust']=raw.gust_sknt*.514444
    # ERA5 hourly sampled then linearly interpolated in time to every minute; space bilinear on u/v.
    hr=pd.date_range(hours[0].floor('h'),hours[-1].ceil('h'),freq='h',tz='UTC')
    loc={'latitude':xr.DataArray(s.lat.to_numpy(),dims='station'),'longitude':xr.DataArray(s.lon.to_numpy()%360,dims='station')}
    if ds is None:ds=xr.open_zarr(uri,chunks=None,storage_options={'token':'anon'})[['10m_u_component_of_wind','10m_v_component_of_wind']]
    era=ds.sel(time=slice(hr[0].tz_localize(None).isoformat(),hr[-1].tz_localize(None).isoformat())).interp(**loc).load()
    assert len(era.time)==len(hr),(day,len(era.time),len(hr))
    u=era['10m_u_component_of_wind'].values;v=era['10m_v_component_of_wind'].values
    grid=[];mins=(hours-hr[0]).total_seconds()/3600
    for j,st in enumerate(s.itertuples(index=False)):
        uu=np.interp(mins,np.arange(len(hr)),u[:,j]);vv=np.interp(mins,np.arange(len(hr)),v[:,j]);grid.append(pd.DataFrame({'station':st.station,'valid':hours,'lat':st.lat,'lon':st.lon,'era':np.hypot(uu,vv)}))
    g=pd.concat(grid,ignore_index=True).merge(raw[['station','valid','obs','gust']],on=['station','valid'],how='left',validate='one_to_one');g.to_csv(gridpath,index=False,compression='gzip')
    info=dict(day=day,station_count=int(len(s)),regional_gust_peak_utc=peak.isoformat(),window_start=hours[0].isoformat(),window_end=hours[-1].isoformat(),minutes=361,minute_rows=int(len(raw)),observed_stations=int(raw.station.nunique()))
    (R/f'window_{tag}_h4.json').write_text(json.dumps(info,indent=2));print(day,info,flush=True)
