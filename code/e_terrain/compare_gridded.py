import subprocess,os,glob,rasterio,pyproj,csv,math
from pathlib import Path
r=Path('/content/e_terrain/wn_avg_pilot_v2');r.mkdir(exist_ok=True)
with open('/content/e_terrain/pilot/forecast_parts/FOUR_v200_GFS_2023100100.csv') as f: rows=list(csv.DictReader(f))
x=next(z for z in rows if z['station']=='CHA' and z['lead_h']=='24');u,v=float(x['fc_u']),float(x['fc_v']);speed=math.hypot(u,v);direct=(270-math.degrees(math.atan2(v,u)))%360
cfg=r/'avg.cfg';cfg.write_text(f'''num_threads = 1\nelevation_file = /content/e_terrain/dem/CHA.tif\nvegetation = grass\nmesh_resolution = 90\nunits_mesh_resolution = m\ninitialization_method = domainAverageInitialization\ninput_speed = {speed}\ninput_speed_units = mps\ninput_direction = {direct}\ninput_wind_height = 10\nunits_input_wind_height = m\noutput_wind_height = 10\nunits_output_wind_height = m\noutput_speed_units = mps\nwrite_ascii_output = true\noutput_path = {r}\n''')
env={**os.environ,'WINDNINJA_DATA':'/content/e_terrain/wn_env/share/windninja','PROJ_DATA':'/content/e_terrain/wn_env/share/proj','PROJ_LIB':'/content/e_terrain/wn_env/share/proj'}
z=subprocess.run(['/content/e_terrain/wn_env/bin/WindNinja_cli',str(cfg)],capture_output=True,text=True,timeout=100,env=env)
print('AVG_RUN',z.returncode,(z.stdout+z.stderr)[-250:],flush=True)
assert z.returncode==0
X,Y=pyproj.Transformer.from_crs('EPSG:4326','EPSG:32632',always_xy=True).transform(7.054367,47.131761)
for name,fn in [('domain_average',glob.glob(str(r/'*_vel.asc'))[0]),('gridded_initialization','/content/e_terrain/wn_grid_pilot_v2/CHA_90m_vel.asc')]:
 with rasterio.open(fn) as d:print(name,'station_ms',float(next(d.sample([(X,Y)]))[0]))
