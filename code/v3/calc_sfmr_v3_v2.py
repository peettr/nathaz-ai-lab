#!/usr/bin/env python3
"""SFMR-only diagnostic v2: prevent gap-induced spurious center selection; preserve initial run."""
import pathlib,csv,json,io,requests
import numpy as np,pandas as pd
from scipy.signal import find_peaks
R=pathlib.Path('/content/L26_18_v3'); O=pathlib.Path('/content/L26_18_v3_corrected');O.mkdir(exist_ok=True)
selected=[x for x in csv.DictReader(open(R/'selected_storm_scenes.csv')) if x['cyclone_name'] in ('MICHAEL','DORIAN','IAN') and x['eye_in_acq']=='True' and x['eye_center']]
flight_map={(x['name'],x['time']):x['flights'].split(';') for x in csv.DictReader(open(R/'eye_scenes_x_sfmr_flights.csv'))}
results=json.loads((R/'sar_results.json').read_text()); assert len(results)==11

def dist(lat,lon,la,lo):
 a=np.deg2rad(lat);b=np.deg2rad(la);q=np.sin((a-b)/2)**2+np.cos(a)*np.cos(b)*np.sin(np.deg2rad(lon-lo)/2)**2
 return 12742*np.arcsin(np.sqrt(np.clip(q,0,1)))
def legs_at(d,stamp,lat,lon,flight,storm):
 t=pd.Timestamp(stamp);g=d.copy();g['radius']=dist(g.latitude.to_numpy(),g.longitude.to_numpy(),lat,lon);out=[]
 for side in ('in','out'):
  z=g[(g.time>=t-pd.Timedelta(minutes=30))&(g.time<=t+pd.Timedelta(minutes=30))&(g.time<=t if side=='in' else g.time>=t)&(g.radius>=5)&(g.radius<=120)&g.smooth.notna()]
  if z.empty:continue
  top=z.loc[z.smooth.idxmax()]
  out.append({'storm':storm,'flight':flight,'leg':side,'crossing_utc':stamp,'n':len(z),'furthest_km':float(z.radius.max()),'nearest_km':float(z.radius.min()),'peak_time_utc':top.time.isoformat(),'peak_radius_km':float(top.radius),'peak_wind_ms':float(top.smooth),'qualifies':bool(z.radius.max()>=70 and z.radius.min()<=15 and top.radius>=10)})
 return out
flight_targets={}
for x in selected:
 for f in flight_map.get((x['cyclone_name'],x['acquisition_start_time']),[]):
  if f and f!='ERR':flight_targets[f]=x['cyclone_name']
all_centers=[];diagnostics=[];flight_data={}
for f,storm in sorted(flight_targets.items()):
 q=f'flight_id,time,latitude,longitude,SWS,FLAG,NGC,RALT&flight_id="{f}"'
 z=requests.get('https://erddap.aoml.noaa.gov/hdb/erddap/tabledap/sfmr_2018_2022.csv?'+requests.utils.requote_uri(q),timeout=180);z.raise_for_status()
 d=pd.read_csv(io.BytesIO(z.content),skiprows=[1]).sort_values('time').reset_index(drop=True);d['time']=pd.to_datetime(d.time,utc=True)
 d.loc[(d.FLAG!=0)|(d.SWS<0)|(d.NGC<4),'SWS']=np.nan;d['smooth']=d.SWS.rolling(11,center=True,min_periods=8).mean()
 # Missing gaps must NOT be filled with 99 m/s; only finite 10-s samples supply minima.
 signal=d.smooth.to_numpy();smooth=np.where(np.isfinite(signal),signal,np.nan)
 peaks,properties=find_peaks(-np.nan_to_num(smooth,nan=0),prominence=15,distance=600)
 times=[pd.Timestamp(x['acquisition_start_time'],tz='UTC') for x in selected if x['cyclone_name']==storm and f in flight_map.get((x['cyclone_name'],x['acquisition_start_time']),[])]
 cand=[]
 for p in peaks:
  a=d.iloc[p];time=a.time
  delta=min(abs((time-t).total_seconds()) for t in times)
  if delta>10800:continue
  ls=legs_at(d,time.isoformat(),float(a.latitude),float(a.longitude),f,storm)
  n=sum(x['qualifies'] for x in ls)
  cand.append({'storm':storm,'flight':f,'time':time.isoformat(),'lat':float(a.latitude),'lon':float(a.longitude),'min_ms':float(a.smooth),'delta_s':delta,'qualifying_legs_fixed_center':n,'legs':ls})
 # Choose qualifying two-sided eye passage nearest the SAR time using SFMR-only center coordinates.
 eligible=[x for x in cand if x['qualifying_legs_fixed_center']==2]
 chosen=min(eligible,key=lambda x:(x['delta_s'],x['min_ms'])) if eligible else None
 diagnostics.append({'flight':f,'candidates':cand,'selected_time':chosen['time'] if chosen else None})
 if chosen:all_centers.append({k:v for k,v in chosen.items() if k!='legs'})
 flight_data[f]=d
 print('CANDIDATES',f,len(cand),'two_side',len(eligible),'selected',chosen['time'] if chosen else None,flush=True)
(O/'sfmr_center_candidates_v2.json').write_text(json.dumps(diagnostics,indent=2))
alllegs=[]
for f,d in flight_data.items():
 storm=flight_targets[f];c=sorted([x for x in all_centers if x['storm']==storm],key=lambda x:x['time'])
 if not c:continue
 sec=d.time.astype('int64').to_numpy()/1e9;ct=np.array([pd.Timestamp(a['time']).timestamp() for a in c]);lat=np.interp(sec,ct,[x['lat'] for x in c]);lon=np.interp(sec,ct,[x['lon'] for x in c]);d['radius']=dist(d.latitude.to_numpy(),d.longitude.to_numpy(),lat,lon)
 for center in [x for x in c if x['flight']==f]:
  t=pd.Timestamp(center['time'])
  for side in ('in','out'):
   z=d[(d.time>=t-pd.Timedelta(minutes=30))&(d.time<=t+pd.Timedelta(minutes=30))&(d.time<=t if side=='in' else d.time>=t)&(d.radius>=5)&(d.radius<=120)&d.smooth.notna()]
   if z.empty:continue
   top=z.loc[z.smooth.idxmax()]
   alllegs.append({'storm':storm,'flight':f,'leg':side,'crossing_utc':center['time'],'n':len(z),'furthest_km':float(z.radius.max()),'nearest_km':float(z.radius.min()),'peak_time_utc':top.time.isoformat(),'peak_radius_km':float(top.radius),'peak_wind_ms':float(top.smooth),'qualifies':bool(z.radius.max()>=70 and z.radius.min()<=15 and top.radius>=10)})
(O/'sfmr_legs.json').write_text(json.dumps({'method':'SFMR-only two-sided candidate then time-nearest center; 11-point smooth; time-interpolated storm proxy','centers':all_centers,'legs':alllegs},indent=2))
groups=[]
for storm in ('MICHAEL','DORIAN','IAN'):
 for a in sorted([x for x in results if x['storm']==storm],key=lambda x:x['time_utc']):
  t=pd.Timestamp(a['time_utc'],tz='UTC')
  if groups and groups[-1]['storm']==storm and abs((t-pd.Timestamp(groups[-1]['time_utc'],tz='UTC')).total_seconds())<1800:groups[-1]['indices'].append(a['index'])
  else:groups.append({'storm':storm,'time_utc':a['time_utc'],'indices':[a['index']]})
assert len(groups)==9
for g in groups:
 t=pd.Timestamp(g['time_utc'],tz='UTC');ls=[a for a in alllegs if a['storm']==g['storm'] and a['qualifies'] and abs((pd.Timestamp(a['crossing_utc'])-t).total_seconds())<=10800]
 g['qualifying_legs']=len(ls);g['flight_ids']=sorted(set(x['flight'] for x in ls));g['peak_radii_km']=[a['peak_radius_km'] for a in ls]
 g['rmw_obs_km']=float(np.median(g['peak_radii_km'])) if ls else None
 g['rmw_sar_km']=float(np.median([results[i]['rmw_km'] for i in g['indices']]))
 g['relative_difference']=abs(g['rmw_sar_km']-g['rmw_obs_km'])/g['rmw_obs_km'] if ls else None
(O/'sfmr_comparison.json').write_text(json.dumps(groups,indent=2))
(O/'done').write_text('DONE\n')
print('CORRECTED_DONE',len(groups),'eligible',sum(g['qualifying_legs']>0 for g in groups),'median',float(np.median([g['relative_difference'] for g in groups if g['relative_difference'] is not None])) if any(g['relative_difference'] is not None for g in groups) else None,flush=True)
