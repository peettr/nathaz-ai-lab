"""CRC scheduled read-only extraction of UrbanTALES to a small, explicit 160x160 benchmark.
Only writes to argv[2] (fresh run root), never into the old project.
"""
import os,sys,json,time,hashlib
from pathlib import Path
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
import xarray as xr
from scipy.ndimage import zoom
src=Path(sys.argv[1]); out=Path(sys.argv[2]); manifest=json.loads(Path(sys.argv[3]).read_text())
ids=sorted(manifest['type_by_case']); X=[]; Y=[]; M=[]; failures=[]
reuse=np.load(sys.argv[4]) if len(sys.argv)>4 else None
reuse_ids={s:i for i,s in enumerate(reuse['case'])} if reuse is not None else {}
def resample(a,order):
 h,w=a.shape; z=zoom(a,(160/h,160/w),order=order,mode='nearest',prefilter=False)
 return z[:160,:160]
for i,c in enumerate(ids):
 try:
  if reuse is not None and reuse['mask'][reuse_ids[c]].any():
   j=reuse_ids[c];X.append(reuse['height'][j]);Y.append(reuse['speed'][j]);M.append(reuse['mask'][j]);continue
  p=src/c; topo=np.loadtxt(p/(c+'_topo'),dtype=np.float32)
  with xr.open_dataset(p/(c+'_ped.nc')) as ds:
   speed=ds['Uped'].values.astype(np.float32)
  if topo.shape != speed.shape:
   if topo.T.shape == speed.shape:topo=topo.T
   else:raise ValueError(f'shape {topo.shape} {speed.shape}')
  solid=topo>0; valid=(~solid)&np.isfinite(speed)&(speed>=0)
  if valid.mean()<.01:raise ValueError(f'valid fraction {valid.mean()}')
  # Weighted interpolation prevents building NaN contamination. Metrics use resized fluid-cell mask.
  weight=resample(valid.astype(np.float32),1)
  sp=resample(np.where(valid,speed,0),1)/np.maximum(weight,1e-5)
  height=resample(topo,1); mask=(resample(solid.astype(np.float32),0)<.5)&(weight>.98)
  if not np.isfinite(sp[mask]).all():raise ValueError('nonfinite resized target')
  X.append(height.astype(np.float16));Y.append(sp.astype(np.float16));M.append(mask)
 except Exception as e:
  failures.append([c,str(e)]);X.append(np.zeros((160,160),np.float16));Y.append(np.zeros((160,160),np.float16));M.append(np.zeros((160,160),bool))
 if (i+1)%25==0:print('processed',i+1,'of',len(ids),'failed',len(failures),flush=True)
np.savez_compressed(out/'urbantales_160.npz',case=np.array(ids),height=np.stack(X),speed=np.stack(Y),mask=np.stack(M))
(out/'extraction.json').write_text(json.dumps({'n':len(ids),'failed':failures,'source':str(src),'dataset_sha256':hashlib.sha256((out/'urbantales_160.npz').read_bytes()).hexdigest()},indent=2))
print('EXTRACTION_COMPLETE',len(ids),'failed',len(failures),'bytes',(out/'urbantales_160.npz').stat().st_size,flush=True)
