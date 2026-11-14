"""HRRR pressure-level truth versus frozen AERO-AIR, NeuralGCM and persistence."""
import pathlib,json,math,datetime
import numpy as np
P=pathlib.Path('/content/l264a100/texas');F=P/'predictions';D=P/'analysis_high'
meta=json.loads((P/'window.json').read_text());wy,wx=meta['west_offset'];ty,tx=meta['texas_offset'];h,w=meta['shape']
yy,xx=np.ogrid[ty:ty+h,tx:tx+w];overlap=(yy>=wy)&(yy<wy+h)&(xx>=wx)&(xx<wx+w)
masks={'strict':~overlap,'overlap':overlap};names=[f'{v}{lev}' for v in ('Z','T') for lev in (300,500,700,850,925)];methods=('aero_air','neuralgcm','persistence')
sse={g:{m:np.zeros((10,72),dtype=np.float64) for m in methods} for g in masks};count={g:int(mask.sum())*10 for g,mask in masks.items()}
for day in range(1,11):
 with np.load(F/f'texas_texas_air_{day:02d}.npz',allow_pickle=False) as z:
  pred=z['pred'];ngcm=z['baseline_ngcm']
 assert pred.shape==ngcm.shape and pred.shape[0]==73 and pred.shape[1] in (10,25) and pred.shape[2:]==(h,w)
 dt=datetime.datetime(2024,4,day)
 with np.load(D/f'{dt:%Y%m%d%H}.npz',allow_pickle=False) as z:init=z['air']
 for lead in range(1,73):
  stamp=dt+datetime.timedelta(hours=lead)
  with np.load(D/f'{stamp:%Y%m%d%H}.npz',allow_pickle=False) as z:obs=z['air']
  for g,mask in masks.items():
   target=obs[:,mask]
   for method,raw in (('aero_air',pred[lead,:10]),('neuralgcm',ngcm[lead,:10]),('persistence',init)):
    diff=raw[:,mask]-target;sse[g][method][:,lead-1]+=np.square(diff,dtype=np.float64).sum(axis=1)
  if lead%24==0:print('AIR_METRIC_DAY',day,'lead',lead,flush=True)
report={'source':'NOAA HRRR wrfprsf00 analysis via noaa-hrrr-bdp-pds, AERO-ODE 99516ae9cf HF checkpoints','n':10,'levels_hPa':[300,500,700,850,925],'variables':names,'lead_hours':list(range(1,73)),'groups':{g:{'grid_cells':int(mask.sum()),'rmse':{m:{name:np.sqrt(sse[g][m][i]/count[g]).tolist() for i,name in enumerate(names)} for m in methods}} for g,mask in masks.items()}}
(P/'texas_air_metrics.json').write_text(json.dumps(report,indent=2));(P/'air_metrics.done').write_text('ok\n');print('AIR_METRICS_DONE',flush=True)
