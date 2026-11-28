"""Read-only source extraction to a distinct, new 320x320 CRC run root."""
import os,sys,json,hashlib
from pathlib import Path
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
import xarray as xr
from scipy.ndimage import zoom
src=Path(sys.argv[1]);out=Path(sys.argv[2]);manifest=json.loads(Path(sys.argv[3]).read_text())
ids=sorted(manifest['type_by_case']);X=[];Y=[];M=[];failures=[]
def resize(a,order):
    h,w=a.shape
    return zoom(a,(320/h,320/w),order=order,mode='nearest',prefilter=False)[:320,:320]
for i,c in enumerate(ids):
    try:
        p=src/c;topo=np.loadtxt(p/(c+'_topo'),dtype=np.float32)
        with xr.open_dataset(p/(c+'_ped.nc')) as ds:
            speed=ds['Uped'].values.astype(np.float32)
        if topo.shape!=speed.shape:
            if topo.T.shape==speed.shape:topo=topo.T
            else:raise ValueError(f'shape {topo.shape} {speed.shape}')
        valid=(topo<=0)&np.isfinite(speed)&(speed>=0)
        if valid.mean()<.01:raise ValueError(f'valid fraction {valid.mean()}')
        weight=resize(valid.astype(np.float32),1)
        sp=resize(np.where(valid,speed,0),1)/np.maximum(weight,1e-5)
        height=resize(topo,1)
        mask=(resize((topo>0).astype(np.float32),0)<.5)&(weight>.98)
        if not mask.any() or not np.isfinite(sp[mask]).all():raise ValueError('invalid resized target/mask')
        X.append(height.astype(np.float16));Y.append(sp.astype(np.float16));M.append(mask)
    except Exception as e:
        failures.append([c,str(e)]);X.append(np.zeros((320,320),np.float16));Y.append(np.zeros((320,320),np.float16));M.append(np.zeros((320,320),bool))
    if (i+1)%25==0:print('processed',i+1,'of',len(ids),'failed',len(failures),flush=True)
path=out/'urbantales_320.npz'
np.savez_compressed(path,case=np.array(ids),height=np.stack(X),speed=np.stack(Y),mask=np.stack(M))
(out/'extraction_320.json').write_text(json.dumps({'n':len(ids),'failed':failures,'source':str(src),'dataset_sha256':hashlib.sha256(path.read_bytes()).hexdigest()},indent=2))
print('EXTRACTION_320_COMPLETE',len(ids),'failed',len(failures),'bytes',path.stat().st_size,flush=True)
