import json, numpy as np, geopandas as gpd
from pathlib import Path
from pyproj import CRS, Transformer
from shapely.ops import transform
from rasterio.features import rasterize
from affine import Affine
P=Path('/content/l2613v2'); m=json.loads((P/'metrics.json').read_text()); src='OpenStreetMap'
a=np.load(P/(src+'_1.npy'),mmap_mode='r')
assert a.shape[:2]==(500,500),a.shape
lat,lon=37.92943,139.05260
local=CRS.from_proj4(f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs')
forward=Transformer.from_crs(CRS.from_epsg(4326),local,always_xy=True)
theta=np.deg2rad(-1);c,s=np.cos(theta),np.sin(theta)
def official(x,y):
 e,n=forward.transform(x,y);return c*e+s*n,-s*e+c*n
g=gpd.read_file(P/(src+'.gpkg')).to_crs(4326)
u=rasterize([(transform(official,x),1) for x in g.geometry if x is not None and not x.is_empty],out_shape=(500,500),transform=Affine(1,0,-250,0,1,-250),dtype='uint8').astype(bool)
solid=np.asarray(a[:,:,2]==-3)
forms={'id':solid,'flip_i':solid[::-1,:],'flip_j':solid[:,::-1],'flip_both':solid[::-1,::-1],'transpose':solid.T,'transpose_flip_i':solid.T[::-1,:],'transpose_flip_j':solid.T[:,::-1],'transpose_flip_both':solid.T[::-1,::-1]}
i,j=np.indices((500,500));disc=np.hypot(j+.5-250,i+.5-250)<190
def iou(v):return float(((v&u)&disc).sum()/max(1,((v|u)&disc).sum()))
vals={k:iou(v) for k,v in forms.items()};pass_=vals['id']>=.7 and vals['id']>max(v for k,v in vals.items() if k!='id')
m['sources'][src]['gate_iou']=vals;m['sources'][src]['gate_pass']=pass_
(P/'metrics.json').write_text(json.dumps(m,indent=2));print(json.dumps({'source':src,'gate_iou':vals,'pass':pass_}))
