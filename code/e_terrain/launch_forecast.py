import os,subprocess,sys
from pathlib import Path
root=Path('/content/e_terrain'); marker=root/'forecast_launch.lock'
with marker.open('x') as f:f.write(str(os.getpid()))
cmd=[sys.executable,str(root/'run_forecasts.py'),'--stations',str(root/'stations_input.csv'),'--start','2023-10-01','--end','2024-04-01','--sources','FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS','GFS','--window','170','179','23','44','--out',str(root/'full')]
log=open(root/'full_forecast.log','x')
p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(root/'forecast_pid').write_text(str(p.pid))
print('LAUNCHED',p.pid,cmd,flush=True)
