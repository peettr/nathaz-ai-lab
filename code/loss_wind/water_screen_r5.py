"""Apply conservative, explicitly assumed water-risk proxies to prepared small cohort."""
import json,collections
from pathlib import Path
import geopandas as gpd
from shapely.geometry import box,Point
from shapely.ops import transform
from pyproj import Transformer
import rasterio
from rasterio.warp import transform as crs_transform
P=Path(__file__).resolve().parent
rows=json.loads((P/'r5_prepared_labels.json').read_text())
with rasterio.open(P/'r5_nhc_idalia_adv16_forecast_inundation.tif') as ds:
 a=[r for r in rows if r['event']=='IDALIA'];xx,yy=crs_transform('EPSG:4326',ds.crs,[r['lon'] for r in a],[r['lat'] for r in a])
 for r,v in zip(a,ds.sample(zip(xx,yy))):r['nhc_forecast_inundation_class']=int(v[0])
land=gpd.read_file('zip://'+str(P.parent/'obs_fusion/h2/ne_10m_land.zip'),bbox=(-90,26,-81,30))
for area in sorted(set(r['area'] for r in rows)):
 a=[r for r in rows if r['area']==area];lat=a[0]['lat'];lon=a[0]['lon']
 cut=box(min(r['lon'] for r in a)-.3,min(r['lat'] for r in a)-.3,max(r['lon'] for r in a)+.3,max(r['lat'] for r in a)+.3)
 coast=land.geometry.intersection(cut);coast=coast[~coast.is_empty].boundary.unary_union
 utm=Transformer.from_crs('EPSG:4326','EPSG:32617' if lon>-85 else 'EPSG:32616',always_xy=True).transform
 boundary=transform(utm,coast)
 for r in a:
  r['shore_distance_km_ne10m']=round(Point(*utm(r['lon'],r['lat'])).distance(boundary)/1000,3)
  r['water_risk_proxy']=(r['nhc_forecast_inundation_class']>0 or r['elevation_m_3dep']<3 or r['shore_distance_km_ne10m']<5)
  # Sensitivity: narrow elevation + coast screen, excluding potential-inundation forecast.
  r['water_risk_geo_only']=(r['elevation_m_3dep']<2 or r['shore_distance_km_ne10m']<3)
 print(area,'N',len(a),'shore',min(r['shore_distance_km_ne10m'] for r in a),max(r['shore_distance_km_ne10m'] for r in a),'strict remain',sum(not r['water_risk_proxy'] for r in a),'geo remain',sum(not r['water_risk_geo_only'] for r in a),'forecast',collections.Counter(r['nhc_forecast_inundation_class'] for r in a),'elev>=3',sum(r['elevation_m_3dep']>=3 for r in a),flush=True)
(P/'r5_water_screen.json').write_text(json.dumps(rows,indent=1))
