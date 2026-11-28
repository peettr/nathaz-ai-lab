import subprocess
p=subprocess.run(['/content/e_terrain/wn_env/bin/WindNinja_cli','--help'],capture_output=True,text=True).stdout
for line in p.splitlines():
 if any(k in line for k in ['input_speed_units','output_speed_units','input_direction','input_wind_height']):print(line)
