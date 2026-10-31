"""OSM PVK morphology (Macdonald 1998 Eq.22-23); Colab only.
OSM level height 3 m and untagged-height median are hypotheses, not observations.
"""
import json,math,collections
from pathlib import Path
import numpy as np
from shapely.geometry import shape,Polygon
from shapely.ops import transform
from shapely.validation import make_valid
from pyproj import Transformer
R=Path('/content/prague_forecasts');R.mkdir(exist_ok=True)
lat,lon=50.072588,14.428428
project=Transformer.from_crs(4326,32633,always_xy=True).transform
X,Y=project(lon,lat)
a=json.loads(Path('/content/prague_buildings.json').read_text())['elements']
features=[];stats=collections.Counter()
for item in a:
 geom=item.get('geometry',[])
 if len(geom)<4:continue
 tags=item.get('tags',{})
 try:
  g=transform(project,shape({'type':'Polygon','coordinates':[[[x['lon'],x['lat']] for x in geom]]}))
  if not g.is_valid:g=make_valid(g)
  h=float(tags.get('height','').replace(' m',''))
  source='height'
 except ValueError:
  try:h=float(tags['building:levels'])*3;source='levels_3m_assumption'
  except (KeyError,ValueError):h=float('nan');source='imputed'
 if not g.is_empty and g.area>1:
  features.append((g,h,source));stats[source]+=1
known=np.array([h for _,h,_ in features if np.isfinite(h) and 2<=h<=120]);median=float(np.median(known))
features=[(g,h if np.isfinite(h) and 2<=h<=120 else median,source if np.isfinite(h) and 2<=h<=120 else 'imputed') for g,h,source in features]
print('FEATURES',len(features),'HEIGHT_TAGS',dict(stats),'IMPUTE_MEDIAN',median,flush=True)
def sector(center):
 angles=np.linspace(center-15,center+15,61)
 def xy(radius,a):return (X+radius*math.sin(math.radians(a)),Y+radius*math.cos(math.radians(a)))
 return Polygon([xy(2000,a) for a in angles]+[xy(500,a) for a in angles[::-1]])
output=[]
for direction in range(0,360,30):
 clip=sector(direction);foot=vol=front=0.;n=0;missing=0
 cross=np.array([math.cos(math.radians(direction)),-math.sin(math.radians(direction))])
 for g,h,source in features:
  if not g.intersects(clip):continue
  q=g.intersection(clip)
  if q.is_empty or q.area<=0:continue
  foot+=q.area;vol+=q.area*h;n+=1;missing+=source=='imputed'
  polys=[q] if q.geom_type=='Polygon' else [v for v in getattr(q,'geoms',[]) if v.geom_type=='Polygon']
  projections=[]
  for pol in polys:projections.extend(np.asarray(pol.exterior.coords)@cross)
  if projections:front+=(max(projections)-min(projections))*h
 lp=foot/clip.area;lf=front/clip.area;H=vol/foot
 dh=1+(lp-1)*4.43**(-lp)
 zH=(1-dh)*math.exp(-((.5*1.2*(1-dh)*lf)/(.4*.4))**(-.5))
 output.append(dict(sector_from_deg=direction,n=n,imputed_n=missing,lambda_p=lp,lambda_f=lf,H_m=H,d_m=dh*H,z0_m=zH*H))
 print('SECTOR',direction,'H',round(H,2),'d',round(dh*H,2),'z0',round(zH*H,2),flush=True)
(R/'morph_sectors.json').write_text(json.dumps({'source':'OSM Overpass 2026-10-15; ODbL','height_assumption':'3m per level; missing use observed-tag median','median_m':median,'features':len(features),'counts':dict(stats),'sectors':output},indent=2))
