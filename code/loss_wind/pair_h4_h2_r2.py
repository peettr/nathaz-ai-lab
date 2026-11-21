#!/usr/bin/env python3
"""H4 minute observations and H2 event inventory reused read-only for DAT feasibility.
Creates new artifacts only; never interpolates H2 station predictions to DAT points.
"""
import csv, gzip, json, math, datetime as dt, pathlib, collections, statistics, requests
P=pathlib.Path(__file__).parent; LAB=P.parent; H4=LAB/'obs_fusion/h4'; H2=LAB/'obs_fusion/h2'
DAT='https://services.dat.noaa.gov/arcgis/rest/services/nws_damageassessmenttoolkit/DamageViewer/FeatureServer/0/query'
DAYS=['20240528','20240601','20250304','20250609','20250709']
def km(a,b,c,d):
 p1,p2=math.radians(a),math.radians(c);x=p2-p1;y=math.radians(d-b)
 return 12742*math.asin(min(1,math.sqrt(math.sin(x/2)**2+math.cos(p1)*math.cos(p2)*math.sin(y/2)**2)))
def clock(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00')).replace(tzinfo=dt.timezone.utc) if '+' not in s and 'Z' not in s else dt.datetime.fromisoformat(s.replace('Z','+00:00'))
def save(name,obj):
 dest=P/name
 if dest.exists():raise FileExistsError(dest)
 dest.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def query_2025(day):
 d=dt.datetime.strptime(day,'%Y%m%d').date();e=d+dt.timedelta(days=1)
 where=f"stormdate >= TIMESTAMP '{d} 00:00:00' AND stormdate < TIMESTAMP '{e} 00:00:00' AND efscale = 'TSTM/Wind'"
 base={'f':'json','where':where}; n=requests.get(DAT,params={**base,'returnCountOnly':'true'},timeout=90).json()['count'];rows=[]
 for off in range(0,n,1000):
  r=requests.get(DAT,params={**base,'outFields':'objectid,stormdate,windspeed,damage_txt,efscale,event_id,lat,lon,comments','returnGeometry':'false','orderByFields':'objectid','resultOffset':off,'resultRecordCount':1000},timeout=90);r.raise_for_status();v=r.json();rows += [x['attributes'] for x in v['features']]
 assert len(rows)==n and len({x['objectid'] for x in rows})==n
 save('dat_h4_2025_'+day+'_r2.json',{'source':DAT,'where':where,'count':n,'features':rows});return rows
def setup():
 census=json.loads((P/'dat_census_2019_2024_r2.json').read_text())['features']
 cache={day:query_2025(day) for day in DAYS if day.startswith('2025')}
 cases={}
 stations={r['station']:r for r in csv.DictReader((H4/'station_clean_h4.csv').open()) if r['status']=='land'}
 for day in DAYS:
  d=dt.datetime.strptime(day,'%Y%m%d').date(); win=json.loads((H4/f'window_{day}_h4.json').read_text());lo=clock(win['window_start']);hi=clock(win['window_end'])
  # Day selection in UTC; geographic region mirrors H4 preregistration. Raw DAT points, not Storm Events reports.
  raw=cache[day] if day.startswith('2025') else census
  pts=[p for p in raw if p['efscale']=='TSTM/Wind' and p['lat'] is not None and p['lon'] is not None and p['stormdate'] is not None and dt.datetime.fromtimestamp(p['stormdate']/1000,dt.timezone.utc).date()==d and 31.5<=p['lat']<=34 and -98.5<=p['lon']<=-95.5]
  obs=collections.defaultdict(list)
  with gzip.open(H4/f'raw_minute_{day}_h4.csv.gz','rt') as f:
   for r in csv.DictReader(f):
    try:
     t=clock(r['valid(UTC)']);g=float(r['gust_sknt']);
     if lo<=t<=hi and r['station'] in stations and 0<g<=150:obs[r['station']].append((t,g))
    except (ValueError,TypeError,KeyError):continue
  cases['H4_'+day]=(pts,stations,obs,lo,hi,'minute_5s_gust','thunderstorm')
 # H2 selected by land scoring counts: Idalia 110 and Helene 95. Beryl 109, but DAT zero in its event window.
 for name,a,b,states in [('IDALIA','2023-08-28','2023-09-02',('FL','GA')),('HELENE','2024-09-25','2024-09-30',('FL','GA','NC','SC','TN'))]:
  lo=clock(a+'T00:00:00+00:00');hi=clock(b+'T00:00:00+00:00')
  raw=[p for p in census if p['efscale']=='Tropical' and p['lat'] is not None and p['lon'] is not None and p['stormdate'] is not None and lo<=dt.datetime.fromtimestamp(p['stormdate']/1000,dt.timezone.utc)<hi and any((s=='FL' and 24<=p['lat']<=31 and -88<=p['lon']<=-80,s=='GA' and 30<=p['lat']<=35 and -86<=p['lon']<=-80,s=='NC' and 33<=p['lat']<=37 and -85<=p['lon']<=-75,s=='SC' and 32<=p['lat']<=36 and -84<=p['lon']<=-78,s=='TN' and 34<=p['lat']<=37 and -91<=p['lon']<=-81)[('FL','GA','NC','SC','TN').index(s)] for s in states)]
  st={r['state']+':'+r['station']:r for r in csv.DictReader((H2/f'stations_{name.lower()}_expanded.csv').open()) if r['state'] in states}
  cleaned={r['station'] for r in csv.DictReader((H2/'station_clean_h2d.csv').open()) if r['status']=='land'}
  st={k:r for k,r in st.items() if k in cleaned}
  obs=collections.defaultdict(list)
  # Existing national IEM monthly gust cache only: reuse as-is, no download.
  for file in (P/'iem_month_cache_r2').glob('*.csv'):
   if not any(file.name.startswith(s+'_') for s in states):continue
   if not any(file.name[3:10].startswith(m) for m in (a[:7],b[:7])):continue
   state=file.name.split('_')[0]
   with file.open() as f:
    for r in csv.DictReader(f):
     key=state+':'+r['station']
     if key not in st:continue
     try:
      t=clock(r['valid']);g=float(r['gust'])
      if lo-dt.timedelta(hours=12)<=t<=hi+dt.timedelta(hours=12) and g>0:obs[key].append((t,g))
     except (ValueError,TypeError):continue
  cases['H2_'+name]=(raw,st,obs,lo,hi,'METAR_gust','tropical')
 return cases

def main():
 cases=setup(); out=[]; summaries=[]
 for case,(pts,stations,obs,lo,hi,kind,hazard) in cases.items():
  matches=[]
  for p in pts:
   t=dt.datetime.fromtimestamp(p['stormdate']/1000,dt.timezone.utc)
   candidates=[]
   for key,s in stations.items():
    d=km(p['lat'],p['lon'],float(s['lat']),float(s['lon']))
    if d>25:continue
    window=dt.timedelta(hours=3 if hazard=='thunderstorm' else 12)
    valid=[(ot,g) for ot,g in obs.get(key,[]) if abs(ot-t)<=window and (hazard!='thunderstorm' or lo<=ot<=hi)]
    if not valid:continue
    nt,ng=min(valid,key=lambda x:(abs(x[0]-t),x[0]));mt,mg=max(valid,key=lambda x:(x[1],-abs((x[0]-t).total_seconds())))
    candidates.append((d,key,nt,ng,mt,mg))
   if not candidates:continue
   d,key,nt,ng,mt,mg=min(candidates,key=lambda x:(x[0],x[1]))
   if hazard=='thunderstorm':foot='<=4km_necessary_not_sufficient' if d<=4 else ('4-10km_beyond_microburst' if d<=10 else '10-25km_beyond_typical_single_downburst')
   else:foot='RMW_unknown_no_same_ring_claim'
   rec={'case':case,'objectid':p['objectid'],'dat_utc':t.isoformat(),'dat_windspeed_damage_inferred':p.get('windspeed'),'distance_km':round(d,3),'station':key,'observation_source':kind,'nearest_gust_kt':ng,'nearest_utc':nt.isoformat(),'window_max_gust_kt':mg,'window_max_utc':mt.isoformat(),'max_minus_nearest_kt':mg-ng,'footprint_context':foot,'rmw_bin':'unknown','colocated_independent':False,'quality_flag':'as_is_>100kt' if mg>100 else 'as_is_unverified'}
   matches.append(rec);out.append(rec)
  stats={'case':case,'hazard':hazard,'dat_points':len(pts),'station_inventory':len(stations),'stations_with_gust':len(obs),'paired_25':len(matches),'reconstructed':0,'source_h4_window':f'{lo.isoformat()}..{hi.isoformat()}' if hazard=='thunderstorm' else None}
  for dis in (5,10,25):
   rr=[r for r in matches if r['distance_km']<=dis]
   stats[f'paired_{dis}']=len(rr);stats[f'groups_{dis}']=len({(r['station'],r['nearest_utc']) for r in rr})
  summaries.append(stats)
  print(stats,flush=True)
 save('h4_h2_pair_summary_r2.json',{'summary':summaries,'H4_raw_url_files':[str(H4/f'iem_minute_url_{d}_h4.txt') for d in DAYS],'H2_land_station_source':str(H2/'results_clean_h2d.md'),'note':'H2 model values exist only at H2 grid stations and have not been interpolated to DAT damage points; reconstructed=0; H4 minute gust restricted to preexisting H4 window; H2 uses preexisting IEM month cache'})
 path=P/'dat_h4_h2_pairs_r2.csv'
 if path.exists():raise FileExistsError(path)
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(out[0]) if out else []);w.writeheader();w.writerows(out)
if __name__=='__main__':main()
