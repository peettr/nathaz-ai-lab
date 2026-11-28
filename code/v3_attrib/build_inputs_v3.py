#!/usr/bin/env python3
"""Read-only v2 archive extraction and published station metadata audit."""
import csv,io,json,zipfile,requests,hashlib
from pathlib import Path
R=Path(__file__).resolve().parent
OLD=Path('./22_Lab/06_Logs/e_terrain')
URL='https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/ogd-smn_meta_stations.csv'
resp=requests.get(URL,timeout=60);resp.raise_for_status()
(R/'meteoswiss_meta_stations_source.csv').write_bytes(resp.content)
meta={r['station_abbr']:r for r in csv.DictReader(io.StringIO(resp.text),delimiter=';')}
sites=list(csv.DictReader((OLD/'stations_frozen.csv').open()))
assert len(sites)==12
z=zipfile.ZipFile(OLD/'e_terrain_v2_deliverables.zip')
inner=zipfile.ZipFile(io.BytesIO(z.read('v2/forecast_parts_v2.zip')))
fc={}
for name in inner.namelist():
 if not (name.startswith('FOUR_v200_GFS_') and name.endswith('.csv')):continue
 for r in csv.DictReader(io.StringIO(inner.read(name).decode())):
  if r['lead_h']=='24':
   key=(r['station'],r['init_utc'][:19].replace('T',' '))
   assert key not in fc,key
   fc[key]=r
rows=list(csv.DictReader((OLD/'v2/paired_main_v2_raw.csv').open()))
assert len(rows)==4295
out=[]
for r in rows:
 key=(r['station'],r['init_utc'][:19].replace('T',' '));f=fc[key]
 r['fc_u']=f['fc_u'];r['fc_v']=f['fc_v'];out.append(r)
with (R/'paired_inputs_v3.csv').open('x',newline='') as g:
 w=csv.DictWriter(g,fieldnames=out[0].keys());w.writeheader();w.writerows(out)
station_rows=[]
for s in sites:
 m=meta[s['station']]
 assert float(m['station_height_masl'])==float(s['elevation_m'])
 # ogd-smn station metadata has station altitude and barometer altitude, but NO anemometer AGL height.
 station_rows.append(dict(station=s['station'],lat=s['lat'],lon=s['lon'],station_elevation_m=s['elevation_m'],wind_sensor_height_m='',wind_height_source_field='元数据缺失（station_height_masl 为站海拔，station_height_barometer_masl 为气压计海拔；均非测风高度）',wind_height_source_url=URL,output_wind_height_m=10,dem_srtm_elevation_m='',srtm_minus_station_m='',dem_pass_50m='',worldcover_1km_code='',worldcover_1km_class='',vegetation='',worldcover_10km_code='',worldcover_10km_class='',worldcover_source_url='',terrain=s['terrain']))
with (R/'stations_metadata_preflight.csv').open('x',newline='') as g:
 w=csv.DictWriter(g,fieldnames=station_rows[0].keys());w.writeheader();w.writerows(station_rows)
print('rows',len(rows),'forecasts',len(fc),'metadata stations',len(meta),'source sha256',hashlib.sha256(resp.content).hexdigest())
