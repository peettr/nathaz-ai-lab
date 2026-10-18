#!/usr/bin/env python3
"""One-case direct gridded AIWP WindNinja initialization sensitivity, CHA 2023-10-02 UTC."""
import os,math,subprocess,glob
from pathlib import Path
import fsspec,h5py,rasterio,numpy as np
from pyproj import Transformer
from scipy.ndimage import map_coordinates
r=Path('/content/e_terrain/wn_grid_pilot_v2');r.mkdir(exist_ok=True)
url='https://noaa-oar-mlwp-data.s3.amazonaws.com/FOUR_v200_GFS/2023/1001/FOUR_v200_GFS_2023100100_f000_f240_06.nc'
h=fsspec.open(url,'rb',block_size=262144).open()
try:
 with h5py.File(h,'r') as f:
  u=f['u10'][4,170:179,23:44];v=f['v10'][4,170:179,23:44]
finally:h.close()
dem='/content/e_terrain/dem/CHA.tif'
with rasterio.open(dem) as d:
 profile=d.profile.copy();H,W=d.shape;H+=8;W+=8
 transform=d.transform*rasterio.Affine.translation(-4,-4)
 profile.update(height=H,width=W,transform=transform)
 ys,xs=np.indices((H,W));X,Y=transform*(xs+.5,ys+.5)
 lon,lat=Transformer.from_crs('EPSG:32632','EPSG:4326',always_xy=True).transform(X,Y)
 iy=(90-lat)*4-170;ix=(lon%360)*4-23
 ui=map_coordinates(u,[iy,ix],order=1,mode='nearest');vi=map_coordinates(v,[iy,ix],order=1,mode='nearest')
 speed=np.hypot(ui,vi).astype('float32');direction=((270-np.degrees(np.arctan2(vi,ui)))%360).astype('float32')
 profile.update(driver='AAIGrid',dtype='float32',count=1,nodata=-32768)
 for name,arr in [('speed',speed),('direction',direction)]:
  with rasterio.open(r/(name+'.asc'),'w',**profile) as out:out.write(arr,1)
cfg=r/'grid.cfg';cfg.write_text(f'''num_threads = 1\nelevation_file = {dem}\nvegetation = grass\nmesh_resolution = 90\nunits_mesh_resolution = m\ninitialization_method = griddedInitialization\ninput_speed_units = mps\noutput_speed_units = mps\ninput_speed_grid = {r/'speed.asc'}\ninput_dir_grid = {r/'direction.asc'}\ninput_wind_height = 10\nunits_input_wind_height = m\noutput_wind_height = 10\nunits_output_wind_height = m\nwrite_ascii_output = true\noutput_path = {r}\n''')
env={**os.environ,'WINDNINJA_DATA':'/content/e_terrain/wn_env/share/windninja','PROJ_DATA':'/content/e_terrain/wn_env/share/proj','PROJ_LIB':'/content/e_terrain/wn_env/share/proj'}
y=subprocess.run(['/content/e_terrain/wn_env/bin/WindNinja_cli',str(cfg)],capture_output=True,text=True,timeout=180,env=env)
(r/'run.log').write_text(y.stdout+'\nSTDERR\n'+y.stderr)
print('GRID_PILOT',y.returncode,'input_station_nearest',float(speed[H//2,W//2]),'tail',(y.stdout+y.stderr)[-1200:],'outputs',glob.glob(str(r/'*_vel.asc')),flush=True)
