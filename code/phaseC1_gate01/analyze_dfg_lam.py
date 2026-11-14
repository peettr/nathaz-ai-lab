import csv,json,math
from pathlib import Path
import numpy as np
from scipy.signal import find_peaks
p=Path(__file__).resolve().parent/'dfg_lam_results';result={}
for d in (20,40):
 for variant in ('ibb','stair'):
  a=np.genfromtxt(p/f'D{d}_{variant}_full.csv',delimiter=',',names=True)
  mask=a['step']>=round(80/.018*d);lift=a['cL'][mask];drag=a['cD'][mask];step=a['step'][mask]
  peaks,_=find_peaks(lift,prominence=max(.05,float(np.std(lift)*.2)),distance=int(.15*d/.018/20))
  periods=np.diff(step[peaks]);st=d/(.018*float(np.median(periods))) if len(periods) else None
  result[f'D{d}_{variant}']={'rows':len(a),'last_step':int(a['step'][-1]),'cDmax':float(np.max(drag)),'cLmax':float(np.max(lift)),'cLmin':float(np.min(lift)),'St':st,'period_steps':periods.tolist(),'finite':bool(np.all(np.isfinite(a['cD'])) and np.all(np.isfinite(a['cL']))),'u_wake_final':float(a['ux_wake'][-1])}
(p/'dfg_lam_metrics.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
