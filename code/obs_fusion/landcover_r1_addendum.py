#!/usr/bin/env python3.10
"""Read-only ESA WorldCover COG crops; derive 1-km station surroundings."""
import csv, io, math, collections, concurrent.futures, time
from pathlib import Path
import requests
from PIL import Image
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'landcover_r1_addendum.csv'
assert not OUT.exists(), 'Refusing to replace existing result'
STATIONS=list(csv.DictReader((ROOT/'stations.csv').open()))
URL='https://planetarycomputer.microsoft.com/api/data/v1/item/crop.tif'
VALID={10,20,30,40,50,60,70,80,90,95,100}

def one(st):
    lat=float(st['lat']);lon=float(st['lon']); dlat=1/111.195;dlon=dlat/math.cos(math.radians(lat))
    xmin,xmax=lon-dlon,lon+dlon;ymin,ymax=lat-dlat,lat+dlat
    south=math.floor(lat/3)*3;west=math.floor(lon/3)*3
    item=f'ESA_WorldCover_10m_2021_v200_N{south:02d}W{-west:03d}'
    geometry={'type':'Feature','geometry':{'type':'Polygon','coordinates':[[[xmin,ymin],[xmax,ymin],[xmax,ymax],[xmin,ymax],[xmin,ymin]]]},'properties':{}}
    params={'collection':'esa-worldcover','item':item,'assets':'map','max_size':256,'dst_crs':'EPSG:4326'}
    for attempt in range(3):
        try:
            r=requests.post(URL,params=params,json=geometry,timeout=90);r.raise_for_status()
            im=Image.open(io.BytesIO(r.content));im.load();break
        except Exception:
            if attempt==2:raise
            time.sleep(2*(attempt+1))
    counts=collections.Counter()
    pix=im.load();w,h=im.size
    for j in range(h):
        plat=ymax-(j+.5)*(ymax-ymin)/h
        for i in range(w):
            plon=xmin+(i+.5)*(xmax-xmin)/w
            if ((plat-lat)/dlat)**2+((plon-lon)/dlon)**2>1:continue
            value=pix[i,j]
            if isinstance(value,tuple):value=value[0]  # LA: classification + mask
            if value in VALID:counts[value]+=1
    n=sum(counts.values())
    if n<100:
        return {'station':st['station'],'dominant_class':'','group':'no_data','built_fraction':'','valid_pixels':n,'item':item,'class_counts':''}
    dominant,count=counts.most_common(1)[0]
    return {'station':st['station'],'dominant_class':dominant,'group':'built_majority_class' if dominant==50 else 'nonbuilt_majority_class','built_fraction':round(counts[50]/n,5),'valid_pixels':n,'item':item,'class_counts':';'.join(f'{k}:{v}' for k,v in sorted(counts.items()))}

with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
    rows=list(ex.map(one,STATIONS))
with OUT.open('x',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
print('stations',len(rows),'groups',collections.Counter(r['group'] for r in rows),'bytes',OUT.stat().st_size,'saved',OUT)
