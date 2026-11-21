"""Coarse categorical sea/land from previously cited Natural Earth 1:10m land polygons."""
import pathlib,csv,shapefile,numpy as np,collections
from shapely.geometry import shape,box
from shapely.ops import unary_union
from shapely import contains_xy
P=pathlib.Path(__file__).resolve().parent
zip_path=P.parents[1]/'b_tc/v1/ne_10m_land.zip'
assert zip_path.exists(),zip_path
region=box(-105,12,-65,45)
land=unary_union([shape(s.__geo_interface__).intersection(region) for s in shapefile.Reader(str(zip_path)).shapes() if shape(s.__geo_interface__).intersects(region)])
rows=list(csv.DictReader(open(P/'inputs_raw.csv')))
lat=np.array([float(r['lat']) for r in rows]);lon=np.array([float(r['lon']) for r in rows]);inside=contains_xy(land,lon,lat)
for r,v in zip(rows,inside):r['land']='land' if v else 'sea'
with open(P/'inputs_land.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
print(collections.Counter((r['catalog'],r['land']) for r in rows))
