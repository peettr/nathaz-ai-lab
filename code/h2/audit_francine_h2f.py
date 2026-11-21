#!/usr/bin/env python3
"""Add Francine-only sites to read-only H2d site audit, without altering earlier rows."""
import csv,io,json,math,collections
from pathlib import Path
import pandas as pd, requests
from PIL import Image
R=Path(__file__).resolve().parent
if __name__=='__main__':
    out=R/'station_clean_h2f.csv'
    assert not out.exists()
    audit=pd.read_csv(R/'station_clean_h2d.csv',keep_default_na=False)
    grid=pd.read_csv(R/'grid_francine_h2f.csv.gz')
    new=grid[~grid.station.isin(audit.station)][['station','lat','lon']].drop_duplicates()
    assert len(new)==6
    metadata={}
    for st in sorted({x.split(':')[0] for x in new.station}):
        for x in requests.get(f'https://mesonet.agron.iastate.edu/geojson/network/{st}_ASOS.geojson',timeout=60).json()['features']:
            metadata[st+':'+x['id']]=x['properties']
    rows=[]
    for _,s in new.iterrows():
        lat,lon=float(s.lat),float(s.lon);dlat=1/111.195;dlon=dlat/math.cos(math.radians(lat))
        xmin,xmax=lon-dlon,lon+dlon;ymin,ymax=lat-dlat,lat+dlat
        south=math.floor(lat/3)*3;west=math.floor(lon/3)*3
        item=f'ESA_WorldCover_10m_2021_v200_N{south:02d}W{-west:03d}'
        geom={'type':'Feature','geometry':{'type':'Polygon','coordinates':[[[xmin,ymin],[xmax,ymin],[xmax,ymax],[xmin,ymax],[xmin,ymin]]]},'properties':{}}
        resp=requests.post('https://planetarycomputer.microsoft.com/api/data/v1/item/crop.tif',params={'collection':'esa-worldcover','item':item,'assets':'map','max_size':256,'dst_crs':'EPSG:4326'},json=geom,timeout=90)
        cover='';counts=collections.Counter();err=''
        if resp.ok:
            im=Image.open(io.BytesIO(resp.content));pix=im.load();w,h=im.size
            for j in range(h):
                plat=ymax-(j+.5)*(ymax-ymin)/h
                for i in range(w):
                    plon=xmin+(i+.5)*(xmax-xmin)/w
                    if ((plat-lat)/dlat)**2+((plon-lon)/dlon)**2>1:continue
                    c=pix[i,j];c=c[0] if isinstance(c,tuple) else c
                    if c in {10,20,30,40,50,60,70,80,90,95,100}:counts[c]+=1
            if sum(counts.values())>=100:cover=counts.most_common(1)[0][0]
        else:err='request_failure_'+str(resp.status_code)
        p=metadata[s.station];name=p.get('sname','') or ''
        offshore=any(t in name.lower() for t in ('green canyon','mississippi canyon','south timbalier'))
        status='platform' if str(cover)=='80' or offshore else ('unknown_cover' if cover=='' else 'land')
        # Compare all existing site locations, including excluded ones.
        for _,old in audit.iterrows():
            d=12742*math.asin(min(1,math.sqrt(math.sin(math.radians(lat-float(old.lat))/2)**2+math.cos(math.radians(lat))*math.cos(math.radians(float(old.lat)))*math.sin(math.radians(lon-float(old.lon))/2)**2)))
            if d<2:raise ValueError(f'new site {s.station} within {d:.3f} km of {old.station}: audit choice needed')
        count=int(grid.loc[grid.station==s.station,'obs'].notna().sum())
        rows.append(dict(station=s.station,lat=lat,lon=lon,name=name,elevation_m=p.get('elevation',''),worldcover_class=cover,valid_pixels=sum(counts.values()),worldcover_item=item,cover_error=err,platform_reason='WorldCover 1km water' if str(cover)=='80' else ('name indicates offshore platform' if offshore else ''),status=status,reason='Francine-only '+('offshore station' if status=='platform' else 'WorldCover result'),valid_hours_all_events=count))
        print(s.station,name,cover,status,count,flush=True)
    result=pd.concat([audit,pd.DataFrame(rows)],ignore_index=True)
    result.to_csv(out,index=False)
    assert set(grid.station).issubset(result.station)
