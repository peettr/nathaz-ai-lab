import csv,json,math
from pathlib import Path
import numpy as np
from scipy.signal import find_peaks
root=Path(__file__).resolve().parent/'dfg_v1_results';res={}
for d in (20,40):
 for variant in ('ibb','stair'):
  p=root/f'D{d}_{variant}_full.csv'
  if not p.exists():continue
  a=np.genfromtxt(p,delimiter=',',names=True)
  steps=np.asarray(a['step']);mask=steps>=round(80/.018*d) # last 2 physical seconds of 10s
  drag=np.asarray(a['cD'])[mask];lift=np.asarray(a['cL'])[mask];sst=steps[mask]
  lp,_=find_peaks(lift,prominence=max(.05,float(np.std(lift)*.2)),distance=max(5,int(.15*math.sqrt(3)*d/.018/20)))
  periods=np.diff(sst[lp]); st=d/(.018*float(np.median(periods))) if len(periods)>0 else None
  res[f'D{d}_{variant}']={'nrows':len(a),'last_step':int(steps[-1]),'finite':bool(np.all(np.isfinite(a.view((float,len(a.dtype.names)))))) if False else bool(np.all(np.isfinite(drag)) and np.all(np.isfinite(lift))),'cd_max':float(np.max(drag)),'cd_min':float(np.min(drag)),'cl_max':float(np.max(lift)),'cl_min':float(np.min(lift)),'st':st,'lift_peak_count':len(lp),'period_steps':periods.tolist(),'last_cd':float(drag[-1]),'last_cl':float(lift[-1])}
(root/'dfg_metrics.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
