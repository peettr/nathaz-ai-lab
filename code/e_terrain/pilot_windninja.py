import requests,gzip,subprocess,math,os,glob
from pathlib import Path
r=Path('/content/e_terrain/wn_pilot');r.mkdir(exist_ok=True)
u='https://elevation-tiles-prod.s3.amazonaws.com/skadi/N47/N47E007.hgt.gz'
p=r/'N47E007.hgt.gz'
if not p.exists():
 x=requests.get(u,timeout=180);print('tile',x.status_code,len(x.content),flush=True);x.raise_for_status();p.write_bytes(x.content)
hgt=r/'N47E007.hgt'
if not hgt.exists():hgt.write_bytes(gzip.decompress(p.read_bytes()))
lon,lat=7.054367,47.131761
# DEM data at 1 arc-second native resolution; 0.03 deg is approximately 3 km.
dem=r/'cha_dem.tif'
cmd=['/usr/bin/gdalwarp','-overwrite','-q','-te',str(lon-.025),str(lat-.025),str(lon+.025),str(lat+.025),'-te_srs','EPSG:4326','-t_srs','EPSG:32632','-tr','30','30','-of','GTiff',str(hgt),str(dem)]
t=subprocess.run(cmd,capture_output=True,text=True,timeout=90);print('warp',t.returncode,t.stderr[:500],flush=True)
assert t.returncode==0
# 10-m wind vector from the smoke forecast, never from observation.
import csv
with open('/content/e_terrain/pilot/forecast_parts/FOUR_v200_GFS_2023100100.csv') as f:
 rows=list(csv.DictReader(f))
x=next(z for z in rows if z['station']=='CHA' and z['lead_h']=='24')
u10,v10=float(x['fc_u']),float(x['fc_v']);speed=math.hypot(u10,v10);direction=(270-math.degrees(math.atan2(v10,u10)))%360
cfg=r/'pilot.cfg'
cfg.write_text(f'''num_threads = 1\nelevation_file = {dem}\nvegetation = grass\nmesh_resolution = 90\nunits_mesh_resolution = m\ninitialization_method = domainAverageInitialization\ninput_speed = {speed}\ninput_speed_units = mps\ninput_direction = {direction}\ninput_wind_height = 10\nunits_input_wind_height = m\noutput_wind_height = 10\nunits_output_wind_height = m\nwrite_ascii_output = true\noutput_path = {r}\n''')
exe='/content/e_terrain/wn_env/bin/WindNinja_cli'
env={**os.environ,'WINDNINJA_DATA':'/content/e_terrain/wn_env/share/windninja','PROJ_DATA':'/content/e_terrain/wn_env/share/proj','PROJ_LIB':'/content/e_terrain/wn_env/share/proj'}
y=subprocess.run([exe,str(cfg)],capture_output=True,text=True,timeout=240,env=env)
(r/'wn_stdout.txt').write_text(y.stdout+'\nSTDERR\n'+y.stderr)
print('run',y.returncode,'input',speed,direction,'tail',(y.stdout+y.stderr)[-3000:],'outputs',glob.glob(str(r/'*')),flush=True)
