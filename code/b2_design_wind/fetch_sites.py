#!/usr/bin/env python3
"""Retrieve frozen IEM airport positions and public ASCE 7-22 ImageServer pixels."""
import csv, json, pathlib, requests, time
OUT=pathlib.Path(__file__).resolve().parent
stations='KBRO KCRP KGLS KLCH KMSY KGPT KMOB KPNS KAAF KTPA KRSW KEYW KMIA KPBI KMLB KJAX KCHS KILM KHSE'.split()
states={'TX':stations[:3],'LA':stations[3:5],'MS':stations[5:6],'AL':stations[6:7],'FL':stations[7:16],'SC':stations[16:17],'NC':stations[17:]}
network={}
for state, ids in states.items():
 url=f'https://mesonet.agron.iastate.edu/geojson/network/{state}_ASOS.geojson'
 response=requests.get(url,timeout=45);response.raise_for_status()
 features=response.json()['features']
 for site in ids:
  # KPBI airport was renamed KDJT in 2026; use same physical IEM site, retain frozen label.
  lookup='DJT' if site=='KPBI' else site[1:]
  matches=[f for f in features if f['id']==lookup or f['id']==site]
  if len(matches)!=1:raise RuntimeError(f'{site} has {len(matches)} matching IEM records')
  f=matches[0]; lon,lat=f['geometry']['coordinates']; network[site]=(lat,lon,state,url)
rows=[]
for site in stations:
 lat,lon,state,source=network[site];row=dict(site=site,state=state,lat=lat,lon=lon,coord_source=source)
 for mri in (50,700):
  base=f'https://gis.asce.org/arcgis/rest/services/ASCE722/w2022_mri{mri}/ImageServer/identify'
  params={'f':'json','geometry':json.dumps({'x':lon,'y':lat,'spatialReference':{'wkid':4326}}),'geometryType':'esriGeometryPoint','returnGeometry':'false'}
  try:
   r=requests.get(base,params=params,timeout=40);r.raise_for_status();payload=r.json();v=float(payload['value']); assert 50<v<250
   row[f'asce_v{mri}_mph']=v;row[f'asce_v{mri}_ms']=round(v*0.44704,4);row[f'asce_v{mri}_source']=base+'?f=json (point identify, WGS84)'
  except Exception as exc:row[f'asce_v{mri}_mph']='';row[f'asce_v{mri}_ms']='';row[f'asce_v{mri}_source']='UNAVAILABLE '+str(exc)[:120]
 rows.append(row);print(site,lat,lon,row['asce_v50_mph'],row['asce_v700_mph'],flush=True)
with (OUT/'sites.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
print('ASCE_COUNT',sum(bool(row['asce_v700_mph']) for row in rows),'IEM_COUNT',len(network),flush=True)
