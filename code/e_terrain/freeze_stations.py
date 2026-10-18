#!/usr/bin/env python3
"""Freeze SwissMetNet sites from documented exposure and cold-season completeness.
Run on Colab. Downloads decade CSV into memory one station at a time; persists
only requested cold-season ten-minute wind/gust records, not entire source files.
Source: MeteoSwiss (CC-BY), https://opendatadocs.meteoswiss.ch/a-data-groundbased/a1-automatic-weather-stations
"""
import csv,io,json,datetime,os,requests
from collections import defaultdict
from zoneinfo import ZoneInfo
from pathlib import Path
ROOT=Path('/content/e_terrain');ROOT.mkdir(exist_ok=True)
BASE='https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/'
SITES={'ridge':['CHA','NAP','DOL','SAE','LAE'],'pass':['BEH','CDM','GSB','VAB','JUN'],'valley':['BLA','GOS','ROB','GRO','VLS'],'plateau':['BUF','SAM','BRL','EIN','SIA']}
start=datetime.datetime(2023,10,1,tzinfo=datetime.timezone.utc)
end=datetime.datetime(2024,4,1,tzinfo=datetime.timezone.utc)
assert not (ROOT/'stations_frozen.csv').exists(), 'freeze already exists'
meta=list(csv.DictReader(io.StringIO(requests.get(BASE+'ogd-smn_meta_stations.csv',timeout=60).text),delimiter=';'))
meta={r['station_abbr']:r for r in meta}
expected=int((end-start).total_seconds()/600)
allstats=[]
for terrain, ids in SITES.items():
 for sid in ids:
  url=f'{BASE}{sid.lower()}/ogd-smn_{sid.lower()}_t_historical_2020-2029.csv'
  print('FETCH',sid,url,flush=True)
  response=requests.get(url,timeout=(30,180))
  response.raise_for_status()
  reader=csv.DictReader(io.StringIO(response.content.decode('utf-8-sig')),delimiter=';')
  assert {'reference_timestamp','fkl010z0','fkl010z1'}.issubset(reader.fieldnames),(sid,reader.fieldnames)
  rows=[]
  for rec in reader:
   stamp=rec['reference_timestamp']
   try: dt=datetime.datetime.strptime(stamp,'%d.%m.%Y %H:%M').replace(tzinfo=datetime.timezone.utc)
   except ValueError:continue
   if not start<=dt<end:continue
   rows.append({'station':sid,'time_utc':dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'speed_ms':rec['fkl010z0'],'gust_1s_ms':rec['fkl010z1'],
                'gust_3s_ms':rec.get('fkl010z3','')})
  good=sum(bool(r['speed_ms']) for r in rows)
  unique=len(set(r['time_utc'] for r in rows))
  assert len(rows)==unique,(sid,len(rows),unique)
  completeness=good/expected
  x=meta[sid]
  print('COUNT',sid,len(rows),good,expected,round(completeness,4),x['station_exposition_en'],flush=True)
  allstats.append((sid,terrain,completeness,rows,x,url))
 # Immediate checkpoint: no forecast error is computed in this script.
selected=[]
for terrain in SITES:
 valid=[x for x in allstats if x[1]==terrain and x[2]>=.9]
 if len(valid)<2:raise RuntimeError(f'Only {len(valid)} eligible stations in {terrain}; no freeze')
 selected.extend(valid[:3])
assert 8<=len(selected)<=12
frozen_at=datetime.datetime.now(ZoneInfo('America/New_York')).strftime('%m-%d %H:%M %Z')
with (ROOT/'stations_frozen.csv').open('x',newline='') as f:
 w=csv.writer(f);w.writerow(['station','lat','lon','elevation_m','wind_sensor_height_m','terrain','selection_reason','coldseason_10min_completeness','valid_10min_count','expected_10min_count','frozen_at_us_eastern','source_url'])
 for sid,terrain,rate,rows,x,url in selected:
  w.writerow([sid,x['station_coordinates_wgs84_lat'],x['station_coordinates_wgs84_lon'],x['station_height_masl'],'unverified',terrain, f"MeteoSwiss exposure: {x['station_exposition_en']}; {terrain} analogue; 10-min mean wind availability >=90%",f'{rate:.6f}',sum(bool(r['speed_ms']) for r in rows),expected,frozen_at,url])
for sid,terrain,rate,rows,x,url in selected:
 with (ROOT/f'obs_{sid}.csv').open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(ROOT/'freeze_manifest.json').write_text(json.dumps({'frozen_at_us_eastern':frozen_at,'expected_10min_count':expected,'candidates':[{'station':s,'terrain':t,'completeness':c,'selected':any(s==z[0] for z in selected)} for s,t,c,_,_,_ in allstats]},indent=2))
print('FROZEN',len(selected),frozen_at,[(x[0],round(x[2],3)) for x in selected],flush=True)
