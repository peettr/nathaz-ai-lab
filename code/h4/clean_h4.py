import io,math,collections,concurrent.futures
from pathlib import Path
import pandas as pd,requests
from PIL import Image
R=Path(__file__).resolve().parent;sites=pd.read_csv(R/'stations_h4.csv');valid={10,20,30,40,50,60,70,80,90,95,100}
prior={}
for path in [R.parent/'h2/station_clean_h2d.csv',R.parent/'h3/station_clean_h3.csv']:
    if path.exists():
        p=pd.read_csv(path)
        for row in p.itertuples(index=False):
            sid=str(row.station).split(':')[-1];cls=getattr(row,'worldcover_class',None)
            if pd.notna(cls):prior[sid]=int(cls)
def cover(x):
    if x.station in prior:return prior[x.station],'prior H2/H3 1km WorldCover'
    lat,lon=x.lat,x.lon;dlat=1/111.195;dlon=dlat/math.cos(math.radians(lat));south=math.floor(lat/3)*3;west=math.floor(lon/3)*3
    item=f'ESA_WorldCover_10m_2021_v200_N{south:02d}W{-west:03d}'
    geom={'type':'Feature','geometry':{'type':'Polygon','coordinates':[[[lon-dlon,lat-dlat],[lon+dlon,lat-dlat],[lon+dlon,lat+dlat],[lon-dlon,lat+dlat],[lon-dlon,lat-dlat]]]},'properties':{}}
    try:
        r=requests.post('https://planetarycomputer.microsoft.com/api/data/v1/item/crop.tif',params={'collection':'esa-worldcover','item':item,'assets':'map','max_size':256,'dst_crs':'EPSG:4326'},json=geom,timeout=90);r.raise_for_status();im=Image.open(io.BytesIO(r.content));pix=im.load();w,h=im.size;c=collections.Counter()
        for j in range(h):
            dy=(j+.5)/h*2-1
            for i in range(w):
                dx=(i+.5)/w*2-1
                if dx*dx+dy*dy>1:continue
                z=pix[i,j];z=z[0] if isinstance(z,tuple) else z
                if z in valid:c[z]+=1
        return (c.most_common(1)[0][0] if sum(c.values())>=100 else None),item
    except Exception as e:return None,'error '+str(e)[:100]
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:cv=list(pool.map(cover,sites.itertuples(index=False)))
sites['worldcover_class']=[x[0] for x in cv];sites['cover_source']=[x[1] for x in cv]
import glob
files=glob.glob(str(R/'grid_*_h4.csv.gz'));grids=[pd.read_csv(p,usecols=['station','obs','gust']) for p in files];a=pd.concat(grids);counts=a.groupby('station').agg(valid=('obs','count'),gust_valid=('gust','count'));sites=sites.merge(counts,on='station',how='left').fillna({'valid':0,'gust_valid':0})
def km(x,y):
    l1,l2=map(math.radians,[x.lat,y.lat]);dl=math.radians(x.lon-y.lon);z=math.sin((l1-l2)/2)**2+math.cos(l1)*math.cos(l2)*math.sin(dl/2)**2
    return 12742*math.asin(min(1,math.sqrt(z)))
parents={s:s for s in sites.station}
def root(s):
    while parents[s]!=s:s=parents[s]
    return s
for i,x in enumerate(sites.itertuples(index=False)):
    for y in list(sites.itertuples(index=False))[i+1:]:
        if km(x,y)<2:parents[root(y.station)]=root(x.station)
sites['status']='land';sites['reason']='';sites.loc[sites.worldcover_class.isna(),'status']='unknown_cover';sites.loc[(sites.worldcover_class==80)|sites.name.fillna('').str.contains('platform|offshore|oil rig|lightship|brazos 451',case=False),'status']='water_platform';sites.loc[sites.station=='T89',['status','reason']]=['suspicious','identical coordinates CVB in H2']
comps=collections.defaultdict(list)
for s in sites.station:comps[root(s)].append(s)
for group in comps.values():
    z=sites[sites.station.isin(group)&(sites.status=='land')]
    if len(z)>1:
        keep=z.sort_values(['valid','station'],ascending=[False,True]).station.iloc[0]
        sites.loc[sites.station.isin(set(z.station)-{keep}),['status','reason']]=['duplicate',f'<2km retain {keep}']
sites.to_csv(R/'station_clean_h4.csv',index=False)
print(sites[['station','worldcover_class','status','valid','gust_valid','reason']].to_string(index=False))
