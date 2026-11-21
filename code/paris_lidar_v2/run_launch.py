import subprocess,sys
from pathlib import Path
root=Path('/content/paris_a1_v2')
for name,args in [('obs',['run_observations.py']),('forecast',['run_forecasts.py','--workers','24','--start','2023-06-01','--end','2024-03-05'])]:
 log=open(root/f'{name}.log','a',buffering=1)
 p=subprocess.Popen([sys.executable,'-u',str(root/args[0])]+args[1:],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 print(name,p.pid,flush=True)
