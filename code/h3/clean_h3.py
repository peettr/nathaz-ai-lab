import io,math,json,collections,concurrent.futures
from pathlib import Path
import numpy as np,pandas as pd,requests
from PIL import Image
R=Path(__file__).resolve().parent
TAGS=['ne_20190128_wide','ne_20210114_wide','ks_20221202','ks_20180306','tx_20191126']
grids=[pd.read_csv(R/f'grid_{t}_h3.csv.gz') for t in TAGS]
a=pd.concat(grids,ignore_index=True); sites=a.groupby('station').agg(lat=('lat','first'),lon=('lon','first'),valid=('obs','count')).reset_index()
meta=pd.read_csv(R/'station_meta_h3.csv').drop_duplicates('station');sites=sites.merge(meta[['station','name','elevation']],on='station',how='left',validate='one_to_one')
prior=pd.read_csv(R/'../h2/station_clean_h2d.csv').set_index('station')
URL='https://planetarycomputer.microsoft.com/api/data/v1/item/crop.tif';VALID={10,20,30,40,50,60,70,80,90,95,100}
def cover(x):
 if x.station in prior.index and pd.notna(prior.loc[x.station,'worldcover_class']):return int(prior.loc[x.station,'worldcover_class']),'H2 existing 1km WorldCover'
 lat=x.lat;lon=x.lon;dlat=1/111.195;dlon=dlat/math.cos(math.radians(lat));xmin,xmax=lon-dlon,lon+dlon;ymin,ymax=lat-dlat,lat+dlat
 south=math.floor(lat/3)*3;west=math.floor(lon/3)*3;item=f'ESA_WorldCover_10m_2021_v200_N{south:02d}W{-west:03d}'
 geom={'type':'Feature','geometry':{'type':'Polygon','coordinates':[[[xmin,ymin],[xmax,ymin],[xmax,ymax],[xmin,ymax],[xmin,ymin]]]},'properties':{}}
 try:
  response=requests.post(URL,params={'collection':'esa-worldcover','item':item,'assets':'map','max_size':256,'dst_crs':'EPSG:4326'},json=geom,timeout=90);response.raise_for_status();im=Image.open(io.BytesIO(response.content));im.load()
  counts=collections.Counter();w,h=im.size;pix=im.load()
  for j in range(h):
   plat=ymax-(j+.5)*(ymax-ymin)/h
   for i in range(w):
    plon=xmin+(i+.5)*(xmax-xmin)/w
    if ((plat-lat)/dlat)**2+((plon-lon)/dlon)**2>1:continue
    v=pix[i,j];v=v[0] if isinstance(v,tuple) else v
    if v in VALID:counts[v]+=1
  return (counts.most_common(1)[0][0] if sum(counts.values())>=100 else None),item
 except Exception as e:return None,str(e)[:100]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:result=list(ex.map(cover,sites.itertuples(index=False)))
sites['worldcover_class']=[x[0] for x in result];sites['cover_source']=[x[1] for x in result]
def km(x,y):
 p1,p2=map(math.radians,(x.lat,y.lat));dl=math.radians(x.lon-y.lon);v=math.sin((p1-p2)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
 return 12742*math.asin(min(1,math.sqrt(v)))
parents={k:k for k in sites.station}
def root(k):
 while parents[k]!=k:k=parents[k]
 return k
for i,x in enumerate(sites.itertuples(index=False)):
 for y in list(sites.itertuples(index=False))[i+1:]:
  if abs(x.lat-y.lat)<.019 and abs(x.lon-y.lon)<.023 and km(x,y)<2:parents[root(y.station)]=root(x.station)
sites['status']='land';sites.loc[sites.worldcover_class.isna(),'status']='unknown_cover';sites.loc[sites.worldcover_class==80,'status']='platform';sites.loc[sites.name.fillna('').str.contains('platform|offshore|oil rig|lightship|brazos 451',case=False),'status']='platform'
sites.loc[sites.station=='TX:T89','status']='excluded_suspicious';sites['reason']=''
for members in collections.defaultdict(list,((k,[]) for k in [])).values():pass
comps=collections.defaultdict(list)
for x in sites.itertuples(index=False):comps[root(x.station)].append(x.station)
for members in comps.values():
 for status in ['land','platform']:
  sub=sites[sites.station.isin(members)&(sites.status==status)]
  if len(sub)>1:
   keep=sub.sort_values(['valid','station'],ascending=[False,True]).station.iloc[0]
   sites.loc[sites.station.isin(set(sub.station)-{keep}),['status','reason']]=['excluded_duplicate',f'<2 km retain {keep}']
sites.to_csv(R/'station_clean_h3.csv',index=False)
print(sites.status.value_counts().to_dict(),flush=True)
