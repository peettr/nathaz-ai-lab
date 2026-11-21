#!/usr/bin/env python3
"""Score H7 with a strict common temporal window and honest unit/height flags."""
import csv,io,json,math,collections,datetime,statistics
from pathlib import Path
import requests,numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent;LAB=P.parents[1]
D=json.loads((P/'raw_progress_h7.json').read_text());pairs={str(x['objectid']):x for x in csv.DictReader((LAB/'loss_wind/dat_iem_pairs_scale_r2.csv').open())}
dat={str(x['objectid']):x for x in json.loads((LAB/'loss_wind/dat_census_2019_2024_r2.json').read_text())['features']}
def dt(s):return datetime.datetime.fromisoformat(s.replace('Z','+00:00').replace(' ','T'))
def km(a,b,c,d):
 a,c=map(math.radians,(a,c));db=math.radians(d-b);da=c-a
 return 12742*math.asin(min(1,math.sqrt(math.sin(da/2)**2+math.cos(a)*math.cos(c)*math.sin(db/2)**2)))
samples=collections.defaultdict(list)
for x in D['samples']:samples[(x['day'],x['id'])].append(x)
rows_a=[];rows_b=[];audit=[];obs_by_day={}
for case in D['cases']:
 day=case['day'];start=dt(case['window_start_utc']);end=dt(case['window_end_utc']);url=(P/f'iem_url_{day}.txt').read_text().strip()
 response=requests.get(url,timeout=120);response.raise_for_status();measure=collections.defaultdict(dict)
 for x in csv.DictReader(line for line in io.StringIO(response.text) if not line.startswith('#')):
  try:
   t=dt(x['valid(UTC)']).replace(tzinfo=datetime.timezone.utc)
   if not start<=t<=end:continue
   mean=float(x['sknt']) if x.get('sknt') else float('nan');gust=float(x['gust_sknt']) if x.get('gust_sknt') else float('nan')
   if not 0<=mean<=120:mean=float('nan')
   if not 0<=gust<=150 or gust<mean:gust=float('nan')
   measure[x['station']][t]=(mean*.514444 if math.isfinite(mean) else None,gust*.514444 if math.isfinite(gust) else None)
  except (ValueError,KeyError):continue
 obs_by_day[day]=measure
 st={x['station']:x for x in D['observations'] if x['day']==day}
 for name,series in measure.items():
  if name not in st:continue
  for typ,idx in [('gust',1),('sustained',0)]:
   valid=[(t,v[idx]) for t,v in series.items() if v[idx] is not None]
   if len(valid)<68:continue
   truth=max(v for _,v in valid);preds=[]
   for t,_ in valid:
    others=[]
    for other,other_series in measure.items():
     if other==name or other not in st:continue
     near=[(abs((ot-t).total_seconds()),val[idx]) for ot,val in other_series.items() if val[idx] is not None and abs((ot-t).total_seconds())<=120]
     if not near:continue
     val=min(near)[1];dist=km(float(st[name]['lat']),float(st[name]['lon']),float(st[other]['lat']),float(st[other]['lon']))
     if dist>=2:others.append((dist,val))
    if len(others)>=3:
     weights=[d**-2 for d,_ in others];preds.append(sum(w*v for w,(_,v) in zip(weights,others))/sum(weights))
   radar=[x for x in samples.get((day,'S'+name),[]) if start<=dt(x['scan_utc'])<=end]
   if not radar or not preds:continue
   rows_a.append({'day':day,'station':name,'variable':typ,'truth_ms':truth,'radar_max_ms':max(x['vr_ms'] for x in radar),'idw_max_ms':max(preds),'min_agl_m':min(x['beam_agl_m'] for x in radar),'max_agl_m':max(x['beam_agl_m'] for x in radar),'valid_minutes':len(valid),'radar_scans':len(radar)})
 for obj in sorted(k[1][1:] for k in samples if k[0]==day and k[1].startswith('D')):
  p=dat.get(obj);rad=samples.get((day,'D'+obj),[])
  if not p or not rad:continue
  stamp=datetime.datetime.fromtimestamp(p['stormdate']/1000,datetime.timezone.utc)
  near=[x for x in rad if abs((dt(x['scan_utc'])-stamp).total_seconds())<=180]
  if not near:continue
  pr=pairs.get(obj)
  if not pr or not pr.get('max_gust_kt') or not pr.get('windspeed'):continue
  try: w=float(pr['windspeed']);station_gust=float(pr['max_gust_kt'])*.514444
  except ValueError:continue
  if not 0<w<200:continue
  chosen=min(near,key=lambda x:abs((dt(x['scan_utc'])-stamp).total_seconds()))
  rows_b.append({'day':day,'objectid':obj,'timestamp_utc':stamp.isoformat(),'radar_abs_vr_ms':chosen['vr_ms'],'beam_agl_m':chosen['beam_agl_m'],'scan_time_delta_s':abs((dt(chosen['scan_utc'])-stamp).total_seconds()),'dat_windspeed_raw':w,'nearest_station_window_gust_ms':station_gust,'nearest_station_km':float(pr['distance_km'])})
 audit.append({'day':day,'dat_candidate_window':case['dat_points_window'],'stations_metadata':case['station_metadata'],'volumes':case['volumes'],'radar_samples':sum(1 for s in D['samples'] if s['day']==day),'dat_matched':sum(r['day']==day for r in rows_b),'station_events_scored':sum(r['day']==day and r['variable']=='gust' for r in rows_a),'decode_failures':len(case['failed'])})
# Replace nearest-station terrain proxy by USGS EPQS ground elevation where available.
# Radar gate was initially sampled under proxy <300 m; this removes any false eligible gates,
# but cannot recover a gate excluded by an overly low proxy elevation.
elev=json.loads((P/'dat_elevation_h7.json').read_text())['elevation_m_by_objectid'] if (P/'dat_elevation_h7.json').exists() else {}
site_meta={f['id']:f['properties'] for f in requests.get('https://mesonet.agron.iastate.edu/geojson/network/ASOS1MIN.geojson',timeout=60).json()['features']}
verified_b=[]
for x in rows_b:
 ground=elev.get(x['objectid']);stations=[o for o in D['observations'] if o['day']==x['day']]
 p=dat[x['objectid']]
 near=min(stations,key=lambda s:km(p['lat'],p['lon'],s['lat'],s['lon']))
 # IEM 1-min metadata elevation; use coordinates to match the public metadata.
 if ground is None:continue
 st_elev=float(site_meta[near['station']]['elevation'])
 true_agl=x['beam_agl_m']+st_elev-ground
 x['beam_agl_m_3dep']=round(true_agl,1);x['ground_elevation_m_3dep']=round(ground,1)
 if 0<=true_agl<300:verified_b.append(x)
rows_b=verified_b
for x in audit:x['dat_matched_3dep_verified']=sum(r['day']==x['day'] for r in rows_b)
def score(group,truth,pred):
 if not group:return None
 error=np.array([x[pred]-x[truth] for x in group]);return {'n':len(group),'bias_ms':round(float(error.mean()),3),'rmse_ms':round(float(np.sqrt(np.mean(error**2))),3)}
A={}
for var in ['gust','sustained']:
 g=[x for x in rows_a if x['variable']==var]
 A[var]={'radar':score(g,'truth_ms','radar_max_ms'),'idw':score(g,'truth_ms','idw_max_ms'),'n':len(g),'ratio_radar_to_gust_median':round(float(np.median([x['radar_max_ms']/x['truth_ms'] for x in g])),3) if g else None}
# Only a conditional sensitivity: DAT schema does not specify mph; never score B gate from assumed unit.
B={'n_spacetime_matched':len(rows_b),'dat_unit_verified':False,'conditional_mph_assumption_only':None}
if rows_b:
 ratios=[x['radar_abs_vr_ms']/x['nearest_station_window_gust_ms'] for x in rows_b if x['nearest_station_window_gust_ms']>0]
 B['radial_to_nearest_gust_ratio_p10_p50_p90']=[round(float(v),3) for v in np.percentile(ratios,[10,50,90])]
 B['beam_agl_3dep_p10_p50_p90_m']=[round(float(v),1) for v in np.percentile([x['beam_agl_m_3dep'] for x in rows_b],[10,50,90])]
 B['nearest_station_distance_p50_km']=round(float(np.median([x['nearest_station_km'] for x in rows_b])),2)
if rows_b:
 errrad=[abs(x['radar_abs_vr_ms']-x['dat_windspeed_raw']*.44704) for x in rows_b];errstation=[abs(x['nearest_station_window_gust_ms']-x['dat_windspeed_raw']*.44704) for x in rows_b]
 B['conditional_mph_assumption_only']={'radar_median_abs_diff_ms':round(float(np.median(errrad)),3),'station_median_abs_diff_ms':round(float(np.median(errstation)),3),'radar_to_station_ratio':round(float(np.median(errrad)/np.median(errstation)),3) if np.median(errstation)>0 else None}
metrics={'protocol':'prereg_h7.md','audit':audit,'A':A,'B':B,'A_rows':rows_a,'B_rows':rows_b,'limitations':['DAT windspeed FeatureServer field has no declared unit','initial DAT gate selection used nearest-ASOS terrain proxy; scoring rechecks USGS EPQS elevation, excluded gates cannot be recovered','single-radar |Vr| at beam height is not ground gust','only 5 ASOS 1-min stations in each radar-near window']}
(P/'metrics_h7.json').write_text(json.dumps(metrics,ensure_ascii=False,allow_nan=False,indent=2)+'\n')
fig,ax=plt.subplots(1,2,figsize=(10,4));g=[x for x in rows_a if x['variable']=='gust']
if g:
 ax[0].scatter([x['truth_ms'] for x in g],[x['radar_max_ms'] for x in g],label='KLOT |Vr| (beam height)');ax[0].scatter([x['truth_ms'] for x in g],[x['idw_max_ms'] for x in g],marker='x',label='IDW LOO');ax[0].plot([0,45],[0,45],ls='--',c='gray');ax[0].legend()
else:
 ax[0].text(.5,.5,'No ASOS station with low-beam radar\nAND sufficient minute observations',ha='center',va='center',transform=ax[0].transAxes)
ax[0].set(xlabel='ASOS 1-min peak gust (m/s)',ylabel='Estimated peak (m/s)',title='A: station, strict common window')
if rows_b:
 ax[1].scatter([x['dat_windspeed_raw'] for x in rows_b],[x['radar_abs_vr_ms'] for x in rows_b],s=8,alpha=.4,label='KLOT |Vr|');ax[1].scatter([x['dat_windspeed_raw'] for x in rows_b],[x['nearest_station_window_gust_ms'] for x in rows_b],s=8,alpha=.4,label='nearest ASOS gust');ax[1].legend()
ax[1].set(xlabel='DAT windspeed (unit NOT specified)',ylabel='radial / ASOS gust (m/s)',title='B: NOT commensurate units; descriptive only')
fig.suptitle('Sources: NWS DAT FeatureServer, NOAA/Unidata KLOT Level II, IEM ASOS 1-min')
fig.tight_layout();fig.savefig(P/'radar_comparison_h7.png',dpi=150);plt.close(fig)
print(json.dumps({'audit':audit,'A':A,'B':B},ensure_ascii=False,indent=2))
