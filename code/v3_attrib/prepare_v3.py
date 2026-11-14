#!/usr/bin/env python3
"""Stage public ESA/SRTM data and WindNinja in ephemeral Colab VM."""
import csv,gzip,hashlib,io,json,math,os,requests,subprocess,tarfile,time
from pathlib import Path
import numpy as np, rasterio,pyproj
from rasterio.windows import Window
from rasterio.transform import rowcol
R=Path('/content/r232d_v3');R.mkdir(exist_ok=True)
meta=list(csv.DictReader((R/'stations_metadata_preflight.csv').open()))
WC='https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/'
TILES=['N45E006','N45E009']
cover={10:'Tree cover',20:'Shrubland',30:'Grassland',40:'Cropland',50:'Built-up',60:'Bare/sparse',70:'Snow/ice',80:'Water',90:'Herbaceous wetland',95:'Mangroves',100:'Moss/lichen'}
wcroot=R/'worldcover';wcroot.mkdir(exist_ok=True)
for tile in TILES:
 name=f'ESA_WorldCover_10m_2021_v200_{tile}_Map.tif';p=wcroot/name
 if not p.exists():
  with requests.get(WC+name,stream=True,timeout=180) as resp:
   resp.raise_for_status()
   with p.open('xb') as f:
    for chunk in resp.iter_content(1024*1024):f.write(chunk)
 print('WC_TILE',name,p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
# Pixel-center, UTM32N metric disk and 10-km square; area weights cos(latitude) in EPSG4326.
xy=pyproj.Transformer.from_crs(4326,32632,always_xy=True)
back=pyproj.Transformer.from_crs(32632,4326,always_xy=True)
for s in meta:
 lon,lat=float(s['lon']),float(s['lat']);x,y=xy.transform(lon,lat)
 tile='N45E006' if lon<9 else 'N45E009'
 p=wcroot/f'ESA_WorldCover_10m_2021_v200_{tile}_Map.tif'
 with rasterio.open(p) as src:
  # sample bounded 10km square; top-left/lower-right and clip to tile
  x0,y0=back.transform(x-5000,y+5000);x1,y1=back.transform(x+5000,y-5000)
  c0,r0=~src.transform*(min(x0,x1),max(y0,y1));c1,r1=~src.transform*(max(x0,x1),min(y0,y1))
  col0=max(0,int(math.floor(c0))-2);col1=min(src.width,int(math.ceil(c1))+2)
  row0=max(0,int(math.floor(r0))-2);row1=min(src.height,int(math.ceil(r1))+2)
  w=Window(col0,row0,col1-col0,row1-row0);arr=src.read(1,window=w)
  tr=src.window_transform(w)
  rr,cc=np.indices(arr.shape);lons=tr.c+(cc+.5)*tr.a;lats=tr.f+(rr+.5)*tr.e
  # To avoid projecting million pixels via pyproj, project each flattened row in manageable array once.
  xx,yy=xy.transform(lons,lats)
  valid=(arr!=0)&(arr!=src.nodata)
  weights=np.cos(np.deg2rad(lats))
  result=[]
  for mask in (((xx-x)**2+(yy-y)**2<=1_000_000),((abs(xx-x)<=5000)&(abs(yy-y)<=5000))):
   codes=arr[valid&mask];ws=weights[valid&mask]
   assert len(codes)>1000,(s['station'],len(codes))
   totals=np.bincount(codes.astype(int),weights=ws,minlength=101)
   winner=int(np.argmax(totals));result.append((winner,cover[winner],len(codes)))
 s.update(worldcover_1km_code=result[0][0],worldcover_1km_class=result[0][1],vegetation='trees' if result[0][0]==10 else 'brush' if result[0][0]==20 else 'grass',worldcover_10km_code=result[1][0],worldcover_10km_class=result[1][1],worldcover_source_url=WC+p.name)
 print('WC_STATION',s['station'],result,flush=True)
# DEM same v2 bounds, source and gdalwarp method; checkpoint tiles.
dem=R/'dem';dem.mkdir(exist_ok=True)
for s in meta:
 sid=s['station'];x,y=xy.transform(float(s['lon']),float(s['lat']));bounds=(x-5000,y-5000,x+5000,y+5000)
 corners=[back.transform(xx,yy) for xx in (x-5100,x+5100) for yy in (y-5100,y+5100)]
 tiles=[]
 for ilat in range(math.floor(min(p[1] for p in corners)),math.floor(max(p[1] for p in corners))+1):
  for ilon in range(math.floor(min(p[0] for p in corners)),math.floor(max(p[0] for p in corners))+1):
   name=f'N{ilat:02d}E{ilon:03d}';gz=dem/(name+'.hgt.gz');hgt=dem/(name+'.hgt')
   if not gz.exists():
    resp=requests.get(f'https://elevation-tiles-prod.s3.amazonaws.com/skadi/N{ilat:02d}/{name}.hgt.gz',timeout=180);resp.raise_for_status();gz.write_bytes(resp.content)
   if not hgt.exists():hgt.write_bytes(gzip.decompress(gz.read_bytes()))
   tiles.append(str(hgt))
 vrt=dem/(sid+'.vrt')
 if not vrt.exists():subprocess.run(['gdalbuildvrt','-q',str(vrt),*tiles],check=True)
 dst=dem/(sid+'.tif')
 if not dst.exists():subprocess.run(['gdalwarp','-q','-te',*(str(v) for v in bounds),'-te_srs','EPSG:32632','-t_srs','EPSG:32632','-tr','30','30','-r','bilinear','-of','GTiff',str(vrt),str(dst)],check=True)
 with rasterio.open(dst) as img:
  # explicitly bilinear at coordinate; v2 used nearest raster.sample, and this is a stated v3 registration diagnostic only.
  ri,ci=img.index(x,y); a=img.read(1,window=Window(ci-1,ri-1,2,2)).astype(float)
  cf,rf=~img.transform*(x,y);dx=cf-(ci-1+.5);dy=rf-(ri-1+.5)
  # choose floor of pixel-center fractional coordinate robustly
  cbase=math.floor(cf-.5);rbase=math.floor(rf-.5);a=img.read(1,window=Window(cbase,rbase,2,2)).astype(float)
  dx=cf-.5-cbase;dy=rf-.5-rbase
  z=float(a[0,0]*(1-dx)*(1-dy)+a[0,1]*dx*(1-dy)+a[1,0]*(1-dx)*dy+a[1,1]*dx*dy)
  assert np.isfinite(z)
 s.update(dem_srtm_elevation_m=z,srtm_minus_station_m=z-float(s['station_elevation_m']),dem_pass_50m=abs(z-float(s['station_elevation_m']))<=50)
 print('DEM_STATION',sid,round(z,2),round(float(s['srtm_minus_station_m']),2),flush=True)
with (R/'stations_v3_inputs.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(meta[0]));w.writeheader();w.writerows(meta)
# Conda-forge WindNinja version used by v2; execution binary and runtime library.
url='https://micro.mamba.pm/api/micromamba/linux-64/latest'
b=requests.get(url,timeout=120);b.raise_for_status()
with tarfile.open(fileobj=io.BytesIO(b.content),mode='r:bz2') as t:
 exe=R/'micromamba';exe.write_bytes(t.extractfile('bin/micromamba').read());exe.chmod(0o755)
cmd=[str(exe),'create','-y','-p',str(R/'wn_env'),'-c','conda-forge','windninja=[地址]']
print('WN_INSTALL_START',time.time(),flush=True)
p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1500,env={**os.environ,'MAMBA_ROOT_PREFIX':str(R/'mamba')})
(R/'wn_install.log').write_text(p.stdout)
print('WN_INSTALL_RC',p.returncode,p.stdout[-900:],flush=True)
assert p.returncode==0
(R/'prepare.done').write_text(json.dumps({'time':time.time(),'stations':len(meta),'version':'[地址]'}))
