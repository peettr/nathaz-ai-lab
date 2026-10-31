"""NOAA GFS 0.25 degree surface HGT representative grid terrain (not native AI model terrain)."""
from pathlib import Path
import requests,eccodes,csv,json,io,numpy as np
r=Path('/content/e_terrain_v2');url='https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20231001/00/atmos/gfs.t00z.pgrb2.0p25.f024'
idx=requests.get(url+'.idx',timeout=60);idx.raise_for_status();lines=idx.text.splitlines()
for i,line in enumerate(lines):
 if ':HGT:surface:' in line:break
else:raise ValueError('HGT surface absent')
a=int(lines[i].split(':')[1]);b=int(lines[i+1].split(':')[1])-1
resp=requests.get(url,headers={'Range':f'bytes={a}-{b}'},timeout=120);assert resp.status_code==206
handle=eccodes.codes_new_from_message(resp.content)
try:
 field=eccodes.codes_get_array(handle,'values').reshape(721,1440)
 with (r/'stations_frozen.csv').open() as h:sites=list(csv.DictReader(h))
 rows=[]
 for s in sites:
  yy=(90-float(s['lat']))*4;xx=float(s['lon'])*4;i=int(yy);j=int(xx);p=yy-i;q=xx-j
  z=(1-p)*(1-q)*field[i,j]+p*(1-q)*field[i+1,j]+(1-p)*q*field[i,j+1]+p*q*field[i+1,j+1]
  rows.append({'station':s['station'],'station_elevation_m':float(s['elevation_m']),'gfs_surface_hgt_bilinear_m':float(z),'station_minus_gfs_m':float(s['elevation_m'])-float(z)})
 (r/'gfs_terrain_v2.json').write_text(json.dumps({'source':url,'note':'GFS grid terrain, proxy for 0.25-degree AI model terrain; not a native FOUR static orography','rows':rows},indent=2))
 print('GFS_TERRAIN',rows,flush=True)
finally:eccodes.codes_release(handle)
