import io,json,math,re
from pathlib import Path
import numpy as np,pandas as pd,requests,xarray as xr
R=Path(__file__).resolve().parent
# Preselected from NOAA candidate table, prioritize TX/OK/KS and separate UTC days.
DATES=[('OK','2024-01-09'),('KS','2024-12-30'),('TX','2024-01-12'),('NE','2024-12-19'),('KS','2018-01-11'),('OK','2023-02-14'),('KS','2022-01-15'),('TX','2022-12-28')]
BOX={'TX':(30,36,-103,-95),'KS':(36,40,-102,-94),'OK':(33,38,-103,-94),'NE':(39,43,-104,-94)}
NETWORK=['TX','OK','KS','NM','CO','AR','MO','NE']
sites=[]
for state in NETWORK:
 u=f'https://mesonet.agron.iastate.edu/geojson/network/{state}_ASOS.geojson';v=requests.get(u,timeout=90).json()['features']
 for f in v:
  p=f['properties'];lon,lat=f['geometry']['coordinates'][:2]
  sites.append(dict(station=state+':'+f['id'],sid=f['id'],state=state,lat=lat,lon=lon,name=p.get('sname',''),elevation=p.get('elevation'),begin=p.get('archive_begin'),end=p.get('archive_end')))
meta=pd.DataFrame(sites)
if not (R/'station_meta_h3.csv').exists():meta.to_csv(R/'station_meta_h3.csv',index=False)
uri='gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3';ds=None
for state,date in DATES:
 tag=state.lower()+'_'+date.replace('-','')+('_wide' if state=='NE' else '');out=R/f'grid_{tag}_h3.csv.gz'
 if out.exists():print('CACHED',tag,flush=True);continue
 a,b,c,d=BOX[state];s=meta[meta.lat.between(a,b)&meta.lon.between(c,d)&(meta.begin.fillna('1900')<=date)&(meta.end.fillna('2100')>=date)].copy()
 print(tag,'sites',len(s),flush=True)
 # Fetch 48h to find regional maximum; split IEM requests into small batches.
 t=pd.Timestamp(date,tz='UTC');parts=[];urls=[]
 for st,g in s.groupby('state'):
  ids=g.sid.tolist()
  for k in range(0,len(ids),35):
   par=dict(station=','.join(ids[k:k+35]),sts=(t-pd.Timedelta(hours=6)).strftime('%Y-%m-%dT%H:%MZ'),ets=(t+pd.Timedelta(hours=30)).strftime('%Y-%m-%dT%H:%MZ'),tz='UTC',format='onlycomma',data='sknt,gust,metar',report_type='3,4')
   rr=requests.get('https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py',params=par,timeout=240);rr.raise_for_status();z=pd.read_csv(io.StringIO(rr.text),comment='#',low_memory=False)
   if not {'station','valid','sknt','gust','metar'}.issubset(z):raise ValueError(rr.text[:300])
   z['station']=st+':'+z.station.astype(str);parts.append(z);urls.append(rr.url)
 obs=pd.concat(parts,ignore_index=True);obs.to_csv(R/f'raw_metar_{tag}_h3.csv.gz',index=False,compression='gzip');(R/f'iem_urls_{tag}_h3.json').write_text(json.dumps(urls,indent=2))
 obs.valid=pd.to_datetime(obs.valid,utc=True,errors='coerce');obs['hour']=(obs.valid+pd.Timedelta(minutes=30)).dt.floor('h');obs['delta']=(obs.valid-obs.hour).abs();obs=obs[obs.delta<=pd.Timedelta(minutes=30)]
 for field,hi in [('sknt',120),('gust',150)]:obs[field]=pd.to_numeric(obs[field],errors='coerce');obs.loc[~obs[field].between(0,hi),field]=np.nan
 obs.loc[obs.gust<obs.sknt,'gust']=np.nan
 obs=obs.sort_values(['station','hour','delta','valid']).drop_duplicates(['station','hour'])
 # Regional hourly median peak over the UTC date ±6h; do not favor method.
 med=obs.groupby('hour').sknt.median();peak=med.idxmax();hours=pd.date_range(peak-pd.Timedelta(hours=12),peak+pd.Timedelta(hours=12),freq='h',tz='UTC')
 oo=obs[obs.hour.isin(hours)].copy();oo['obs']=oo.sknt*0.514444;oo['obs_gust']=oo.gust*0.514444
 ts=oo.metar.fillna('').str.contains(r'\bTS\w*|\bCB\b',case=False,regex=True)
 print(tag,'regional peak',peak,'TS/CB reports',int(ts.sum()),'sites wind',oo[oo.obs.notna()].station.nunique(),flush=True)
 # Reduce to stations with at least one report in window, but retain outages for audit.
 s=s[s.station.isin(oo.station.unique())].copy();loc={'latitude':xr.DataArray(s.lat.to_numpy(),dims='station'),'longitude':xr.DataArray(s.lon.to_numpy()%360,dims='station')}
 if ds is None:ds=xr.open_zarr(uri,chunks=None,storage_options={'token':'anon'})[['10m_u_component_of_wind','10m_v_component_of_wind']]
 era=ds.sel(time=slice(hours[0].tz_localize(None).isoformat(),hours[-1].tz_localize(None).isoformat())).interp(**loc).load();assert len(era.time)==25
 speed=np.hypot(era['10m_u_component_of_wind'].values,era['10m_v_component_of_wind'].values)
 grid=pd.DataFrame([{'event':tag,'station':x.station,'hour':h,'lat':x.lat,'lon':x.lon,'era':float(speed[i,j])} for i,h in enumerate(hours) for j,x in enumerate(s.itertuples(index=False))])
 grid=grid.merge(oo[['station','hour','obs','obs_gust','metar']],on=['station','hour'],how='left',validate='one_to_one');grid.to_csv(out,index=False,compression='gzip')
 (R/f'window_{tag}_h3.json').write_text(json.dumps(dict(peak_utc=peak.isoformat(),start=hours[0].isoformat(),end=hours[-1].isoformat(),stations=int(s.shape[0]),ts_cb=int(ts.sum())),indent=2))
