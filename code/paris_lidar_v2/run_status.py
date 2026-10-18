from pathlib import Path
import json,os,time
r=Path('/content/paris_a1_v2')
for name in ('obs','forecast'):
 log=r/(name+'.log');lines=log.read_text().splitlines() if log.exists() else []
 print(name,'log_lines',len(lines),'last:',*lines[-5:],sep='\n',flush=True)
print('OBS_FILES',[p.name for p in sorted(r.glob('obs_*.csv'))],flush=True)
for s in ('FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS','GFS'):
 folder=r/'parts'/s
 print(s,'csv',len(list(folder.glob('*.csv'))),'errors',len(list(folder.glob('*.error'))),flush=True)
 for f in list(folder.glob('*.error'))[:2]:print('ERROR',f.name,f.read_text()[-500:],flush=True)
print('PROGRESS',(r/'forecast_progress.json').read_text() if (r/'forecast_progress.json').exists() else 'none',flush=True)
