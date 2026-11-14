"""12 immutable 10-km UTM square DEMs from SRTM 1 arc-second, 30m sampling."""
import csv,gzip,math,requests,subprocess
from pathlib import Path
import pyproj,rasterio
r=Path('/content/e_terrain_v2'); dem=r/'dem';dem.mkdir(exist_ok=True)
with (r/'stations_frozen.csv').open() as f:sites=list(csv.DictReader(f))
t=pyproj.Transformer.from_crs(4326,32632,always_xy=True);back=pyproj.Transformer.from_crs(32632,4326,always_xy=True)
for s in sites:
 sid=s['station'];x,y=t.transform(float(s['lon']),float(s['lat']));bounds=(x-5000,y-5000,x+5000,y+5000)
 corners=[back.transform(xx,yy) for xx in (x-5100,x+5100) for yy in (y-5100,y+5100)]
 tiles=[]
 for ilat in range(math.floor(min(p[1] for p in corners)),math.floor(max(p[1] for p in corners))+1):
  for ilon in range(math.floor(min(p[0] for p in corners)),math.floor(max(p[0] for p in corners))+1):
   name=f'N{ilat:02d}E{ilon:03d}';gz=dem/(name+'.hgt.gz');hgt=dem/(name+'.hgt')
   if not gz.exists():
    resp=requests.get(f'https://elevation-tiles-prod.s3.amazonaws.com/skadi/N{ilat:02d}/{name}.hgt.gz',timeout=180);resp.raise_for_status();gz.write_bytes(resp.content)
   if not hgt.exists():hgt.write_bytes(gzip.decompress(gz.read_bytes()))
   tiles.append(str(hgt))
 vrt=dem/(sid+'.vrt');subprocess.run(['gdalbuildvrt','-q',str(vrt),*tiles],check=True)
 out=dem/(sid+'.tif')
 if out.exists():raise FileExistsError(out)
 subprocess.run(['gdalwarp','-q','-te',*(str(v) for v in bounds),'-te_srs','EPSG:32632','-t_srs','EPSG:32632','-tr','30','30','-r','bilinear','-of','GTiff',str(vrt),str(out)],check=True)
 with rasterio.open(out) as img:
  height=float(next(img.sample([(x,y)]))[0]);assert img.width>300 and img.height>300
 (dem/(sid+'.json')).write_text(__import__('json').dumps({'utm_bounds_m':bounds,'srtm_center_elevation_m':height,'station_elevation_m':float(s['elevation_m'])}))
 print('DEM_V2',sid,img.width,img.height,round(height),flush=True)
print('DEM_V2_COMPLETE',len(sites),flush=True)
