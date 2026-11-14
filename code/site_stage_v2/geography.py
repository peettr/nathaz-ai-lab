"""Compute coastline/lakes distances from Natural Earth 10m geometries on Colab."""
import csv,json,io,zipfile,urllib.request,math
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import transform,unary_union
from pyproj import Transformer,CRS
root=Path('/content/site_stage_v2');rows=list(csv.DictReader((root/'homr_gates.csv').open()))
def dataset(name):
 p=root/(name+'.zip')
 if not p.exists():
  url=f'https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_{name}.zip'
  with urllib.request.urlopen(url,timeout=180) as r:p.write_bytes(r.read())
 with zipfile.ZipFile(p) as f:f.extractall(root/name)
 return gpd.read_file(root/name/('ne_10m_'+name+'.shp'))
coast=dataset('coastline');lakes=dataset('lakes');print('geo',len(coast),len(lakes),list(lakes.columns),flush=True)
# naturalearth lake name(s) and type verified against loaded attributes
mask=lakes['name'].astype(str).str.upper().str.contains('SUPERIOR|MICHIGAN|HURON|ERIE|ONTARIO|ST. CLAIR')
great=lakes[mask];print('great names',great['name'].tolist(),flush=True)
for r in rows:
 try:
  lat=float(r['lat']);lon=float(r['lon']);projection=CRS.from_proj4(f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs');tr=Transformer.from_crs('EPSG:4326',projection,always_xy=True).transform
  window=coast.cx[lon-.6:lon+.6,lat-.6:lat+.6];window2=great.cx[lon-.3:lon+.3,lat-.3:lat+.3]
  r['coast_km']=round(min((transform(tr,g).distance(Point(0,0)) for g in window.geometry),default=float('inf'))/1000,3)
  r['great_lake_km']=round(min((transform(tr,g.boundary).distance(Point(0,0)) for g in window2.geometry),default=float('inf'))/1000,3)
  r['geog_ok']=str(r['coast_km']>=10 and r['great_lake_km']>=5).lower()
 except Exception as e:r['geog_error']=repr(e)
fields=list(rows[0]);fields+=['coast_km','great_lake_km','geog_ok','geog_error']
with (root/'geography.csv').open('w',newline='') as f:w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
for g in ('plains','other'):
 q=[r for r in rows if r['region']==g and all(r.get(k)=='true' for k in ('instrument_ok','relocation_ok','elevation_ok','geog_ok'))]
 print(g,len(q),[r['station'] for r in q],flush=True)
