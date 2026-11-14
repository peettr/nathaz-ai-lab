#!/usr/bin/env python3
"""Colab-only v3 driver; extends L26.18-01 SAR and SFMR readouts without changing thresholds."""
import csv,io,json,pathlib,requests,runpy,datetime as dt,subprocess,sys,traceback
import numpy as np,pandas as pd
from scipy.signal import find_peaks
R=pathlib.Path('/content/L26_18_v3'); R.mkdir(exist_ok=True)
selected=list(csv.DictReader(open(R/'selected_storm_scenes.csv')))
selected=[r for r in selected if r['cyclone_name'] in ('MICHAEL','DORIAN','IAN') and r['eye_in_acq']=='True' and r['eye_center']]
assert len(selected)==11
flights=list(csv.DictReader(open(R/'eye_scenes_x_sfmr_flights.csv')))
bykey={(r['name'],r['time']):r['flights'].split(';') for r in flights}
api={}
for storm,sid in [('MICHAEL','al142018'),('DORIAN','al052019'),('IAN','al092022')]:
 z=requests.get('https://cyclobs.ifremer.fr/app/api/getData',params={'sid':sid,'include_cols':'all','product_type':'gridded'},timeout=90);z.raise_for_status()
 api[storm]=list(csv.DictReader(io.StringIO(z.text)))
 print('API',storm,len(api[storm]),flush=True)
rows=[]
for x in selected:
 candidates=[a for a in api[x['cyclone_name']] if a.get('data_url')==x['data_url']]
 assert len(candidates)==1,(x['cyclone_name'],x['acquisition_start_time'],len(candidates))
 a=candidates[0]
 assert a['eye_center']==x['eye_center']
 rows.append(a)
(R/'target_meta.json').write_text(json.dumps(rows,indent=2))
# Keep source extraction and processing in this VM; no raw data transported to host.
runpy.run_path('/content/L26_18_v3/calc_sar_bc_v3.py',run_name='__main__')
results=json.loads((R/'sar_results.json').read_text())
BASE='https://erddap.aoml.noaa.gov/hdb/erddap/tabledap/sfmr_2018_2022.csv'
alllegs=[];centers=[];flight_data={}; candidate_log=[]
flight_targets={}
for s in selected:
 for flight in bykey.get((s['cyclone_name'],s['acquisition_start_time']),[]):
  if flight and flight!='ERR':flight_targets[flight]=s['cyclone_name']
print('FLIGHTS',len(flight_targets),sorted(flight_targets),flush=True)
for flight,storm in sorted(flight_targets.items()):
 q='flight_id,time,latitude,longitude,SWS,FLAG,NGC,RALT&flight_id="'+flight+'"'
 z=requests.get(BASE+'?'+requests.utils.requote_uri(q),timeout=180);print('SFMR_FETCH',flight,z.status_code,len(z.content),flush=True);z.raise_for_status()
 d=pd.read_csv(io.BytesIO(z.content),skiprows=[1]);d['time']=pd.to_datetime(d.time,utc=True);d=d.sort_values('time').reset_index(drop=True)
 assert set(d.flight_id)=={flight}
 # The previous Ian script's 11-point mean, FLAG/NGC quality and >=15 m/s minimum prominence diagnostic.
 d.loc[(d.FLAG!=0)|(d.SWS<0)|(d.NGC<4),'SWS']=np.nan
 d['smooth']=d.SWS.rolling(11,center=True,min_periods=8).mean()
 x=d.smooth.interpolate(limit=5).fillna(99).to_numpy()
 peaks,props=find_peaks(-x,prominence=15,distance=600)
 targets=[pd.Timestamp(s['acquisition_start_time'],tz='UTC') for s in selected if s['cyclone_name']==storm and flight in bykey.get((s['cyclone_name'],s['acquisition_start_time']),[])]
 candidates=[]
 for j,p in enumerate(peaks):
  a=d.iloc[p]
  if not np.isfinite(a.smooth) or not any(abs((a.time-t).total_seconds())<=3*3600 for t in targets):continue
  candidates.append((float(props['prominences'][j]),p))
 candidate_log.append({'flight':flight,'candidates':[{'time':d.iloc[p].time.isoformat(),'lat':float(d.iloc[p].latitude),'lon':float(d.iloc[p].longitude),'prominence':v,'smooth':float(d.iloc[p].smooth)} for v,p in candidates]})
 if candidates:
  # Independent proxy: deepest prominent near-eye wind minimum per flight, no SAR location used.
  _,p=max(candidates)
  a=d.iloc[p];centers.append({'storm':storm,'flight':flight,'time':a.time.isoformat(),'lat':float(a.latitude),'lon':float(a.longitude),'smooth_min_ms':float(a.smooth)})
 flight_data[flight]=d
 print('CENTER',flight,centers[-1] if candidates else None,flush=True)
(R/'sfmr_centers.json').write_text(json.dumps({'method':'11-point SFMR quality-filtered wind-speed mean; local minima prominence >=15 m/s, distance >=600 samples, maximum prominence within 3h of listed SAR time per flight; no SAR/ATCF/b-deck center','centers':centers,'candidates':candidate_log},indent=2))
def radius(lat,lon,la,lo):
 a=np.deg2rad(lat);b=np.deg2rad(la)
 h=np.sin((a-b)/2)**2+np.cos(a)*np.cos(b)*np.sin(np.deg2rad(lon-lo)/2)**2
 return 12742*np.arcsin(np.sqrt(np.clip(h,0,1)))
for flight,d in flight_data.items():
 storm=flight_targets[flight]
 c=sorted([c for c in centers if c['storm']==storm],key=lambda a:a['time'])
 if not c:continue
 sec=d.time.astype('int64').to_numpy()/1e9
 csec=np.array([pd.Timestamp(a['time']).timestamp() for a in c])
 d['radius']=radius(d.latitude.to_numpy(),d.longitude.to_numpy(),np.interp(sec,csec,[a['lat'] for a in c]),np.interp(sec,csec,[a['lon'] for a in c]))
 for center in [a for a in c if a['flight']==flight]:
  cross=pd.Timestamp(center['time'])
  for side in ('in','out'):
   g=d[(d.time>=cross-pd.Timedelta(minutes=30))&(d.time<=cross+pd.Timedelta(minutes=30))&(d.time<=cross if side=='in' else d.time>=cross)&(d.radius>=5)&(d.radius<=120)&d.smooth.notna()]
   if g.empty:continue
   top=g.loc[g.smooth.idxmax()]
   alllegs.append({'storm':storm,'flight':flight,'leg':side,'crossing_utc':center['time'],'n':len(g),'furthest_km':float(g.radius.max()),'nearest_km':float(g.radius.min()),'peak_time_utc':top.time.isoformat(),'peak_radius_km':float(top.radius),'peak_wind_ms':float(top.smooth),'qualifies':bool(g.radius.max()>=70 and g.radius.min()<=15 and top.radius>=10)})
(R/'sfmr_legs.json').write_text(json.dumps({'center_method':'SFMR-only wind-minimum flight-location proxies; time-interpolated across storm fixes; no b-deck or SAR centers','legs':alllegs},indent=2))
# Nine time groups, paired same-time SAR scenes as median; two-scene groups are defined by start times within 30 minutes.
groups=[]
for storm in ('MICHAEL','DORIAN','IAN'):
 for a in sorted([x for x in results if x['storm']==storm],key=lambda x:x['time_utc']):
  t=pd.Timestamp(a['time_utc'],tz='UTC')
  if groups and groups[-1]['storm']==storm and abs((t-pd.Timestamp(groups[-1]['time_utc'],tz='UTC')).total_seconds())<1800:
   groups[-1]['indices'].append(a['index'])
  else:groups.append({'storm':storm,'time_utc':a['time_utc'],'indices':[a['index']]})
assert len(groups)==9 and sum(len(x['indices']) for x in groups)==11
for group in groups:
 t=pd.Timestamp(group['time_utc'],tz='UTC')
 legs=[x for x in alllegs if x['storm']==group['storm'] and x['qualifies'] and abs((pd.Timestamp(x['crossing_utc'])-t).total_seconds())<=3*3600]
 rmws=[results[i]['rmw_km'] for i in group['indices'] if results[i]['rmw_km'] is not None]
 group.update({'qualifying_legs':len(legs),'flight_ids':sorted(set(x['flight'] for x in legs)),'peak_radii_km':[x['peak_radius_km'] for x in legs],'rmw_obs_km':float(np.median([x['peak_radius_km'] for x in legs])) if legs else None,'rmw_sar_km':float(np.median(rmws)) if rmws else None})
 group['relative_difference']=abs(group['rmw_sar_km']-group['rmw_obs_km'])/group['rmw_obs_km'] if group['rmw_obs_km'] and group['rmw_sar_km'] else None
(R/'sfmr_comparison.json').write_text(json.dumps(groups,indent=2))
print('BC_DONE',len(results),len(groups),'eligible',sum(g['relative_difference'] is not None for g in groups),'sensitivity_median',float(np.median([x['max_relative_change'] for x in results if x['max_relative_change'] is not None])),'obs_diff_median',float(np.median([g['relative_difference'] for g in groups if g['relative_difference'] is not None])) if any(g['relative_difference'] is not None for g in groups) else None,flush=True)
(R/'done').write_text('BC_DONE\n')
