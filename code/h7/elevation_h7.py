#!/usr/bin/env python3
"""USGS EPQS point elevations for scored DAT sites; only adjust terrain proxy after radar sampling."""
import csv,json,collections,concurrent.futures,requests,time
from pathlib import Path
P=Path(__file__).resolve().parent;LAB=P.parents[1];d=json.loads((P/'metrics_h7.json').read_text());points={str(p['objectid']):p for p in json.loads((LAB/'loss_wind/dat_census_2019_2024_r2.json').read_text())['features']}
ids=sorted({x['objectid'] for x in d['B_rows']});url='https://epqs.nationalmap.gov/v1/json'
def fetch(obj):
 p=points[obj]
 try:
  r=requests.get(url,params={'x':p['lon'],'y':p['lat'],'units':'Meters','wkid':4326},timeout=35);r.raise_for_status();v=float(r.json()['value']);return obj,v
 except Exception as e:return obj,None
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:results=dict(ex.map(fetch,ids))
(P/'dat_elevation_h7.json').write_text(json.dumps({'source':url,'elevation_m_by_objectid':results},indent=2)+'\n')
print('EPQS',len(ids),'available',sum(x is not None for x in results.values()))
