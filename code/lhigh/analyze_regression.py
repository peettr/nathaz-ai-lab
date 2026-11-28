"""Recompute frozen DFG D40 gate from preserved A100 CSV."""
import json,zipfile,io,hashlib,numpy as np
from scipy.signal import find_peaks
from pathlib import Path
r=Path(__file__).resolve().parent
p=r/'lhigh_regression.zip'
with zipfile.ZipFile(p) as z:
 channel=json.loads(z.read('channel_metrics.json'))
 a=np.genfromtxt(io.BytesIO(z.read('lam_D40_ibb_full.csv')),delimiter=',',names=True)
 assert z.read('complete.txt').strip()==b'complete'
 assert int(a['step'][-1])==222222 and len(a)==11112
 assert np.isfinite(a['cD']).all() and np.isfinite(a['cL']).all()
 mask=a['step']>=round(80/.018*40)
 step=a['step'][mask];lift=a['cL'][mask];drag=a['cD'][mask]
 peaks,_=find_peaks(lift,prominence=max(.05,float(np.std(lift)*.2)),distance=int(.15*40/.018/20))
 periods=np.diff(step[peaks]); assert len(periods)>2
 vals={'cDmax':float(np.max(drag)),'cLmax':float(np.max(lift)),'St':40/(.018*float(np.median(periods))),'period_steps':periods.tolist(),'rows':len(a),'last_step':int(a['step'][-1])}
 limits={'cDmax':[3.1234,3.3362],'cLmax':[.9405,1.0605],'St':[.2862,.3139]}
 out={'source_archive':str(p),'archive_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'fixture':'Lhigh high-q 5b, low-q 6a; FP32 SRT; DFG D40, 80-100 s window','channel':channel,'dfg_D40':vals,'bounds':limits,'pass_each':{k:limits[k][0]<=vals[k]<=limits[k][1] for k in limits}}
 (r/'lhigh_metrics.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({'dfg_D40':vals,'pass_each':out['pass_each'],'orders':{k:v for k,v in channel.items() if k.startswith('order')}},indent=2))
