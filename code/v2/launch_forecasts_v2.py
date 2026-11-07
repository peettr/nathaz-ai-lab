from pathlib import Path
import subprocess,sys
r=Path('/content/e_terrain_v2')
(r/'forecast_v2.lock').open('x').write('v2-revision')
log=(r/'forecast_v2.log').open('x')
cmd=[sys.executable,str(r/'run_forecasts_v2.py'),'--stations',str(r/'stations_frozen.csv'),'--start','2023-10-01','--end','2024-04-01','--sources','FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS','GFS','--out',str(r/'full'),'--window','170','180','22','44']
p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(r/'forecast_v2.pid').write_text(str(p.pid));print('FORECAST_V2_LAUNCHED',p.pid,flush=True)
