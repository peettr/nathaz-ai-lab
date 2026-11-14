import subprocess,os,time,math,json
from pathlib import Path
r=Path('/content/e_terrain_v2'); d=r/'pilot_v2';d.mkdir(exist_ok=False)
speed=7.;direction=270.
(d/'windninja.cfg').write_text(f'num_threads = 1\nelevation_file = {r/"dem/CHA.tif"}\nvegetation = grass\nmesh_resolution = 100\nunits_mesh_resolution = m\ninitialization_method = domainAverageInitialization\ninput_speed = {speed}\ninput_speed_units = mps\ninput_direction = {direction}\ninput_wind_height = 10\nunits_input_wind_height = m\noutput_wind_height = 10\nunits_output_wind_height = m\noutput_speed_units = mps\nwrite_ascii_output = true\noutput_path = {d}\n')
env={**os.environ,'WINDNINJA_DATA':str(r/'wn_env/share/windninja'),'PROJ_DATA':str(r/'wn_env/share/proj'),'PROJ_LIB':str(r/'wn_env/share/proj')}
t=time.monotonic();p=subprocess.run([str(r/'wn_env/bin/WindNinja_cli'),str(d/'windninja.cfg')],env=env,capture_output=True,text=True,timeout=180)
print('PILOT',p.returncode,round(time.monotonic()-t,2),[q.name for q in d.glob('*_vel.asc')],(p.stdout+p.stderr)[-500:],flush=True)
