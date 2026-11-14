#!/usr/bin/env python3
"""Add true center-to-track nearest point for each accepted leg (no r>=5 censor)."""
import pathlib,json,io,requests,numpy as np,pandas as pd
R=pathlib.Path('/content/L26_18_vdm'); groups=json.loads((R/'comparison_vdm.json').read_text()); fixes=json.loads((R/'official_fixes.json').read_text()); legs=json.loads((R/'sfmr_legs_vdm.json').read_text())['legs']
def radius(lat,lon,la,lo):
 a=np.deg2rad(lat);b=np.deg2rad(la);h=np.sin((a-b)/2)**2+np.cos(a)*np.cos(b)*np.sin(np.deg2rad(lon-lo)/2)**2
 return 12742*np.arcsin(np.sqrt(np.clip(h,0,1)))
for flight in sorted(set(x['flight'] for x in legs if x['qualifies'])):
 q=f'flight_id,time,latitude,longitude,SWS,FLAG,NGC&flight_id="{flight}"'
 z=requests.get('https://erddap.aoml.noaa.gov/hdb/erddap/tabledap/sfmr_2018_2022.csv?'+requests.utils.requote_uri(q),timeout=180);z.raise_for_status()
 d=pd.read_csv(io.BytesIO(z.content),skiprows=[1]);d['time']=pd.to_datetime(d.time,utc=True)
 storm=next(x['storm'] for x in legs if x['flight']==flight); ff=sorted([x for x in fixes if x['storm']==storm],key=lambda x:x['time']);sec=d.time.astype('int64').to_numpy()/1e9;ft=[pd.Timestamp(x['time']).timestamp() for x in ff]
 d['radius']=radius(d.latitude.to_numpy(),d.longitude.to_numpy(),np.interp(sec,ft,[x['lat'] for x in ff]),np.interp(sec,ft,[x['lon'] for x in ff]))
 for leg in (x for x in legs if x['flight']==flight and x['qualifies']):
  ts=pd.Timestamp(leg['crossing_utc']);window=d[(d.time>=ts-pd.Timedelta(minutes=30))&(d.time<=ts+pd.Timedelta(minutes=30))&(d.time<=ts if leg['leg']=='in' else d.time>=ts)]
  leg['true_nearest_km']=float(window.radius.min()) if not window.empty else None
 print('AUDIT',flight,flush=True)
lookup={(x['flight'],x['leg'],x['crossing_utc']):x['true_nearest_km'] for x in legs if x['qualifies']}
for g in groups:
 for x in g['leg_details']:x['true_nearest_km']=lookup[(x['flight'],x['leg'],x['crossing_utc'])]
(R/'comparison_vdm_true_nearest.json').write_text(json.dumps(groups,indent=2))
(R/'true_nearest_done').write_text('DONE\n')
print('NEAREST_DONE',sum(len(g['leg_details']) for g in groups),flush=True)
