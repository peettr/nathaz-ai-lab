"""Read-only original-grid extraction, one case at a time, no spatial resize."""
import os,sys,json,hashlib,io,zipfile
from pathlib import Path
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
import xarray as xr
src=Path(sys.argv[1]);out=Path(sys.argv[2]);split=json.loads(Path(sys.argv[3]).read_text())
assert src.is_dir() and out.is_dir()
ids=sorted(split['type_by_case']);assert len(ids)==528
archive=out/'urbantales_native_v4.zip';manifest=out/'extraction_v4.json'
assert not archive.exists() and not manifest.exists(), 'output exists: refuse overwrite'
rows=[]
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=3,allowZip64=True) as z:
 for i,c in enumerate(ids):
  p=src/c;topo=np.loadtxt(p/(c+'_topo'),dtype=np.float32)
  with xr.open_dataset(p/(c+'_ped.nc')) as ds:
   sp=ds['Uped'].values.astype(np.float32)
   coord={k:np.asarray(ds[k].values) for k in ('x','y')}
   attrs={'global':dict(ds.attrs),'Uped':dict(ds['Uped'].attrs)}
  if topo.shape!=sp.shape:
   if topo.T.shape==sp.shape:topo=topo.T
   else:raise ValueError((c,topo.shape,sp.shape))
  # The archived x/y span 0..H and 0..W inclusive; infer cell size from span/count.
  pitch=[float((v[-1]-v[0])/len(v)) for v in coord.values()]
  if not all(.98<x<1.02 for x in pitch):raise ValueError((c,pitch))
  m=(topo<=0)&np.isfinite(sp)&(sp>=0)
  if m.mean()<.01:raise ValueError((c,float(m.mean())))
  buf=io.BytesIO();np.savez(buf,height=topo.astype(np.float16),speed=np.where(m,sp,0).astype(np.float16),mask=m)
  z.writestr(c+'.npz',buf.getvalue())
  rows.append({'case':c,'shape':list(sp.shape),'pitch_m':pitch,'valid_fraction':float(m.mean()),'source_attrs':attrs})
  if (i+1)%25==0:print('NATIVE_PROCESSED',i+1,'bytes',archive.stat().st_size,flush=True)
sha=hashlib.sha256()
with archive.open('rb') as f:
 for block in iter(lambda:f.read(4*1024*1024),b''):sha.update(block)
manifest.write_text(json.dumps({'source':str(src),'n':len(rows),'cases':rows,'archive_bytes':archive.stat().st_size,'sha256':sha.hexdigest()},indent=2,default=str))
print('NATIVE_COMPLETE',len(rows),archive.stat().st_size,sha.hexdigest(),flush=True)
