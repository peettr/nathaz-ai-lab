#!/usr/bin/env python3
"""Recompute v3 B with NHC aircraft VDM fixes; no storm-track or SAR center used."""
import csv, io, json, re, time, pathlib
import requests, numpy as np, pandas as pd
R=pathlib.Path('/content/L26_18_vdm'); R.mkdir(exist_ok=True)
SAR=json.loads((R/'sar_results.json').read_text())
selected=[x for x in csv.DictReader(open(R/'selected_storm_scenes.csv')) if x['cyclone_name'] in ('MICHAEL','DORIAN','IAN') and x['eye_in_acq']=='True' and x['eye_center']]
flights={(x['name'],x['time']):[f for f in x['flights'].split(';') if f and f!='ERR'] for x in csv.DictReader(open(R/'eye_scenes_x_sfmr_flights.csv'))}
assert len(SAR)==11 and len(selected)==11
G=[]
for storm in ('MICHAEL','DORIAN','IAN'):
 for a in sorted((x for x in SAR if x['storm']==storm),key=lambda x:x['time_utc']):
  t=pd.Timestamp(a['time_utc'],tz='UTC')
  if G and G[-1]['storm']==storm and abs((t-pd.Timestamp(G[-1]['time_utc'],tz='UTC')).total_seconds())<1800:G[-1]['indices'].append(a['index'])
  else:G.append({'storm':storm,'time_utc':a['time_utc'],'indices':[a['index']]})
assert len(G)==9
ids={'MICHAEL':'AL142018','DORIAN':'AL052019','IAN':'AL092022'}
period={'MICHAEL':('20181008','20181010'),'DORIAN':('20190829','20190901'),'IAN':('20220925','20220928')}

def radius(lat,lon,la,lo):
 a=np.deg2rad(lat);b=np.deg2rad(la);h=np.sin((a-b)/2)**2+np.cos(a)*np.cos(b)*np.sin(np.deg2rad(lon-lo)/2)**2
 return 12742*np.arcsin(np.sqrt(np.clip(h,0,1)))
s=requests.Session();fix=[];sources=[]
for storm,sid in ids.items():
 year=sid[-4:];base=f'https://www.nhc.noaa.gov/archive/recon/{year}/REPNT2/'
 res=s.get(base,timeout=90);res.raise_for_status()
 names=sorted(set(re.findall(r'href="(REPNT2-[^" ]+\.txt)"',res.text)))
 lo,hi=period[storm]
 names=[n for n in names if lo<=re.search(r'\.(\d{8})',n).group(1)<=hi]
 print('VDM_INDEX',storm,len(names),flush=True)
 for n in names:
  url=base+n;rr=s.get(url,timeout=40);rr.raise_for_status();text=rr.text
  if sid not in text:continue
  mt=re.search(r'\bA\.\s*(\d\d)/(\d\d:\d\d(?::\d\d)?)Z',text)
  pos=re.search(r'\bB\.\s*(\d{1,2}(?:\.\d+)?)\s*deg\s*([NS])\s*(\d{1,3}(?:\.\d+)?)\s*deg\s*([EW])',text)
  if not (mt and pos):continue
  issue=re.search(r'\.(\d{8})(\d{4})\.txt',n)
  d=pd.Timestamp(f'{issue[1][:6]}{mt[1]} {mt[2]}',tz='UTC')
  if abs((d-pd.Timestamp(issue[1]+issue[2],tz='UTC')).total_seconds())>24*3600:
   print('DATE_MISMATCH',n,d,flush=True);continue
  lat=float(pos[1])*(1 if pos[2]=='N' else -1);lon=float(pos[3])*(1 if pos[4]=='E' else -1)
  record={'storm':storm,'time':d.isoformat(),'lat':lat,'lon':lon,'url':url,'message_id':n,'raw_A':mt.group(0),'raw_B':pos.group(0)}
  if not any(x['storm']==storm and x['time']==record['time'] and x['lat']==lat and x['lon']==lon for x in fix):fix.append(record)
 print('VDM_FIX',storm,sum(x['storm']==storm for x in fix),flush=True)
(R/'official_fixes.json').write_text(json.dumps(fix,indent=2))
for g in G:
 t=pd.Timestamp(g['time_utc'],tz='UTC');c=[f for f in fix if f['storm']==g['storm'] and abs((pd.Timestamp(f['time'])-t).total_seconds())<=10800]
 g['official_fixes_3h']=len(c);g['official_fix_urls']=[f['url'] for f in c]
print('VDM_COUNTS',[(g['storm'],g['time_utc'],g['official_fixes_3h']) for g in G],flush=True)
BASE='https://erddap.aoml.noaa.gov/hdb/erddap/tabledap/sfmr_2018_2022.csv'
targets={}
for row in selected:
 for f in flights.get((row['cyclone_name'],row['acquisition_start_time']),[]):targets[f]=row['cyclone_name']
legs=[];flight_reports=[]
for flight,storm in sorted(targets.items()):
 q=f'flight_id,time,latitude,longitude,SWS,FLAG,NGC,RALT&flight_id="{flight}"'
 resp=s.get(BASE+'?'+requests.utils.requote_uri(q),timeout=180);resp.raise_for_status()
 d=pd.read_csv(io.BytesIO(resp.content),skiprows=[1]).sort_values('time').reset_index(drop=True);d['time']=pd.to_datetime(d.time,utc=True)
 d.loc[(d.FLAG!=0)|(d.SWS<0)|(d.NGC<4),'SWS']=np.nan
 d['smooth']=d.SWS.rolling(11,center=True,min_periods=8).mean()
 ff=sorted([f for f in fix if f['storm']==storm],key=lambda x:x['time'])
 report={'flight':flight,'storm':storm,'n':len(d),'fix_candidates':[]}
 if not ff:flight_reports.append(report);continue
 sec=d.time.astype('int64').to_numpy()/1e9;ft=np.array([pd.Timestamp(f['time']).timestamp() for f in ff])
 cl=np.interp(sec,ft,[f['lat'] for f in ff]);co=np.interp(sec,ft,[f['lon'] for f in ff]);d['radius']=radius(d.latitude.to_numpy(),d.longitude.to_numpy(),cl,co)
 # Fix is a crossing candidate only if the measured aircraft track was near the official vortex center.
 accepted=[]
 for f in ff:
  ts=pd.Timestamp(f['time']);target_near=any(g['storm']==storm and abs((ts-pd.Timestamp(g['time_utc'],tz='UTC')).total_seconds())<=10800 for g in G)
  if not target_near:continue
  near=d[(d.time>=ts-pd.Timedelta(minutes=15))&(d.time<=ts+pd.Timedelta(minutes=15))]
  if near.empty:continue
  pathdist=radius(near.latitude.to_numpy(),near.longitude.to_numpy(),f['lat'],f['lon'])
  close=float(np.nanmin(pathdist))
  report['fix_candidates'].append({'fix_url':f['url'],'time':f['time'],'flight_nearest_to_fix_km':close})
  if close>15:continue
  # Reject duplicate archive messages/corrections and adjacent fix reports for one physical crossing.
  if accepted and (ts-pd.Timestamp(accepted[-1]['time'])).total_seconds()<45*60:continue
  accepted.append(f)
  for side in ('in','out'):
   z=d[(d.time>=ts-pd.Timedelta(minutes=30))&(d.time<=ts+pd.Timedelta(minutes=30))&(d.time<=ts if side=='in' else d.time>=ts)&(d.radius>=5)&(d.radius<=120)&d.smooth.notna()]
   if z.empty:continue
   top=z.loc[z.smooth.idxmax()]
   legs.append({'storm':storm,'flight':flight,'leg':side,'crossing_utc':f['time'],'fix_url':f['url'],'fix_to_flight_nearest_km':close,'n':len(z),'furthest_km':float(z.radius.max()),'nearest_km':float(z.radius.min()),'peak_time_utc':top.time.isoformat(),'peak_radius_km':float(top.radius),'peak_wind_ms':float(top.smooth),'qualifies':bool(z.radius.max()>=70 and z.radius.min()<=15 and top.radius>=10)})
 flight_reports.append(report)
 print('SFMR_FLIGHT',flight,len(d),len(report['fix_candidates']),len(accepted),flush=True)
(R/'sfmr_legs_vdm.json').write_text(json.dumps({'method':'NHC URNT12/REPNT2 official vortex fixes; temporal interpolation; same FLAG/NGC/SWS, smoothing, radial/leg thresholds as v3 first run','legs':legs,'flight_reports':flight_reports},indent=2))
for g in G:
 t=pd.Timestamp(g['time_utc'],tz='UTC');ll=[x for x in legs if x['storm']==g['storm'] and x['qualifies'] and abs((pd.Timestamp(x['crossing_utc'])-t).total_seconds())<=10800]
 g['qualifying_legs']=len(ll);g['leg_details']=[{k:x[k] for k in ('flight','leg','crossing_utc','fix_url','nearest_km','fix_to_flight_nearest_km','peak_radius_km')} for x in ll]
 g['rmw_obs_km']=float(np.median([x['peak_radius_km'] for x in ll])) if ll else None
 g['rmw_sar_km']=float(np.median([SAR[i]['rmw_km'] for i in g['indices']]))
 g['relative_difference']=abs(g['rmw_sar_km']-g['rmw_obs_km'])/g['rmw_obs_km'] if ll else None
(R/'comparison_vdm.json').write_text(json.dumps(G,indent=2))
valid=[g['relative_difference'] for g in G if g['relative_difference'] is not None]
summary={'time_groups':len(G),'groups_with_official_fixes':sum(g['official_fixes_3h']>0 for g in G),'groups_with_qualifying_legs':len(valid),'relative_difference_median':float(np.median(valid)) if valid else None,'leg_count':len(legs)}
(R/'summary_vdm.json').write_text(json.dumps(summary,indent=2));(R/'done').write_text('DONE\n')
print('VDM_DONE',summary,flush=True)
