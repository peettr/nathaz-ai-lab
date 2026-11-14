import csv,gzip,math,requests,subprocess,os
from pathlib import Path
root=Path('/content/e_terrain');demroot=root/'dem';demroot.mkdir(exist_ok=True)
with (root/'stations_frozen.csv').open() as f:sites=list(csv.DictReader(f))
for x in sites:
 sid=x['station'];lat=float(x['lat']);lon=float(x['lon'])
 tiles=[]
 for ilat in range(math.floor(lat-.015),math.floor(lat+.015)+1):
  for ilon in range(math.floor(lon-.015),math.floor(lon+.015)+1):
   tile=f'N{ilat:02d}E{ilon:03d}'
   url=f'https://elevation-tiles-prod.s3.amazonaws.com/skadi/N{ilat:02d}/{tile}.hgt.gz'
   gz=demroot/(tile+'.hgt.gz');hgt=demroot/(tile+'.hgt')
   if not gz.exists():
    r=requests.get(url,timeout=180);r.raise_for_status();gz.write_bytes(r.content)
   if not hgt.exists():hgt.write_bytes(gzip.decompress(gz.read_bytes()))
   tiles.append(str(hgt))
 vrt=demroot/(sid+'.vrt')
 p=subprocess.run(['/usr/bin/gdalbuildvrt','-q',str(vrt),*tiles],capture_output=True,text=True,timeout=30)
 assert p.returncode==0,(sid,p.stderr)
 out=demroot/(sid+'.tif')
 if out.exists():
  print('ALREADY_DEM',sid,flush=True);continue
 cmd=['/usr/bin/gdalwarp','-q','-te',str(lon-.015),str(lat-.015),str(lon+.015),str(lat+.015),'-te_srs','EPSG:4326','-t_srs','EPSG:32632','-tr','30','30','-r','bilinear','-of','GTiff',str(vrt),str(out)]
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=120);assert p.returncode==0,(sid,p.stderr)
 print('DEM',sid,len(tiles),out.stat().st_size,flush=True)
print('DEM_READY',len(sites),flush=True)
