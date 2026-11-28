import json, math, gzip, hashlib, time, io, requests, pandas as pd
from pathlib import Path
from shapely.geometry import shape, box
from shapely.ops import transform
from shapely.strtree import STRtree
from pyproj import Transformer
P=Path('/content/step1c'); P.mkdir(exist_ok=True)
t0=time.time(); bbox=(-112.07468914574454,33.456745973618524,-112.06931085425546,33.46125402556067)
roi=box(*bbox)
def tile(lon,lat,z=9):
 lat=math.radians(lat); return int((lon+180)/360*(1<<z)),int((1-math.asinh(math.tan(lat))/math.pi)/2*(1<<z))
def qkey(x,y,z=9):
 return int(''.join(str(((x & (1<<i))>0)+2*((y & (1<<i))>0)) for i in range(z-1,-1,-1)))
xy=[tile(x,y) for x in (bbox[0],bbox[2]) for y in (bbox[1],bbox[3])]; keys=sorted({qkey(x,y) for x in range(min(v[0] for v in xy),max(v[0] for v in xy)+1) for y in range(min(v[1] for v in xy),max(v[1] for v in xy)+1)})
url='https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv.'
r=requests.get(url,timeout=30);r.raise_for_status();cat=pd.read_csv(io.BytesIO(r.content));print('CAT',len(cat),keys,cat.columns.tolist(),flush=True)
raw=[]; tiles=[]
for key in keys:
 rows=cat.loc[pd.to_numeric(cat.QuadKey,errors='coerce')==key].copy()
 if len(rows)>1:
  def size(s):
   n,u=str(s).split();return float(n)*{'KB':1024,'MB':1024**2,'GB':1024**3}.get(u.upper(),1)
  rows=rows.loc[[rows.Size.map(size).idxmax()]]
 for _,row in rows.iterrows():
  u=row.Url; h=requests.get(u,timeout=60); h.raise_for_status(); data=h.content
  if u.endswith('.gz') or data[:2]==b'\x1f\x8b':data=gzip.decompress(data)
  tiles.append({'quadkey':key,'url':u,'bytes':len(h.content),'sha256':hashlib.sha256(h.content).hexdigest(),'records':len(data.splitlines())})
  for line in data.splitlines():
   feat=json.loads(line);g=shape(feat['geometry']);
   if g.intersects(roi):raw.append((g,feat.get('properties',{})))
print('RAW',len(raw),flush=True)
transformer=Transformer.from_crs('EPSG:4326','EPSG:32612',always_xy=True)
def geo(g):return transform(transformer.transform,g)
A=[geo(x[0]) for x in raw];tree=STRtree(A)
def matches(f):
 existing=json.loads(Path(f).read_text())['features']; arr=[]; same=0;ious=[]; heights=0
 for ft in existing:
  p=geo(shape(ft['geometry'])); cand=tree.query(p); best=0; ex=False; bestidx=None
  for idx in cand:
   g=A[int(idx)]; inter=p.intersection(g).area; union=p.union(g).area; iou=inter/union if union else 0
   if iou>best:best=iou;bestidx=int(idx)
  if bestidx is not None:
   ex=bool(p.equals(A[bestidx]));
   if ex:
    x=ft['properties'].get('buildingheight');y=raw[bestidx][1].get('height');
    if str(x)!='NA' and y!=-1 and x is not None and abs(float(x)-float(y))<0.11:heights+=1
  same+=ex;ious.append(best)
 return {'count':len(existing),'exact_geometry':same,'exact_ratio':same/len(existing),'median_best_iou':float(pd.Series(ious).median()),'matched_iou_ge_0_99':sum(i>=.99 for i in ious),'height_match_at_exact':heights,'unmatched_iou_zero':sum(i==0 for i in ious)}
out={'bbox':bbox,'catalog_url':url,'catalog_bytes':len(r.content),'catalog_sha256':hashlib.sha256(r.content).hexdigest(),'quadkeys':keys,'tiles':tiles,'raw_intersect_roi_count':len(raw),'ms':matches('/content/step1c/ms.geojson'),'usa':matches('/content/step1c/usa.geojson'),'elapsed_sec':round(time.time()-t0,2)}
(P/'comparison.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2),flush=True)
