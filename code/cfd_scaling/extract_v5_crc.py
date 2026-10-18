"""UrbanTALES source extraction with PALM ASCII north-to-south row correction.
Read-only source. Never reuse masked v4 speed. Fail closed on low topo/Uped IoU.
"""
import os, sys, json, hashlib, io, zipfile
from pathlib import Path
os.environ['OMP_NUM_THREADS']='1'; os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
import xarray as xr
src=Path(sys.argv[1]); out=Path(sys.argv[2]); split=json.loads(Path(sys.argv[3]).read_text())
assert src.is_dir() and out.is_dir()
ids=sorted(split['type_by_case']); assert len(ids)==528
archive=out/'urbantales_native_v5.zip'; manifest=out/'extraction_v5.json'
assert not archive.exists() and not manifest.exists(), 'output exists: refuse overwrite'
rows=[]; excluded=[]
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=3,allowZip64=True) as z:
 for i,c in enumerate(ids):
  p=src/c
  topo=np.loadtxt(p/(c+'_topo'),dtype=np.float32)
  with xr.open_dataset(p/(c+'_ped.nc')) as ds:
   sp=np.asarray(ds['Uped'].values,dtype=np.float32)
   coord={k:np.asarray(ds[k].values) for k in ('x','y')}
   attrs={'global':dict(ds.attrs),'Uped':dict(ds['Uped'].attrs)}
  # Only original orientation (then y reversal), or transpose (then y reversal).
  # Select against the independent Uped invalid-pixel footprint, not field score.
  invalid=~np.isfinite(sp) | (sp<0)
  candidates=[('flip_y',topo[::-1,:])]
  if topo.T.shape==sp.shape:candidates.append(('transpose_flip_y',topo.T[::-1,:]))
  comparisons=[]
  for name,h in candidates:
   if h.shape!=sp.shape:continue
   built=h>0
   union=np.count_nonzero(built|invalid)
   iou=np.count_nonzero(built&invalid)/union if union else 1.
   comparisons.append((float(iou),name,h))
  if not comparisons:raise ValueError((c,topo.shape,sp.shape))
  iou,orientation,h=max(comparisons,key=lambda t:t[0])
  pitch=[float((v[-1]-v[0])/len(v)) for v in coord.values()]
  if not all(.98<x<1.02 for x in pitch):raise ValueError((c,pitch))
  row={'case':c,'shape':list(sp.shape),'pitch_m':pitch,'topo_uped_invalid_iou':iou,'orientation':orientation,
       'candidate_ious':{name:score for score,name,_ in comparisons},'invalid_fraction':float(invalid.mean()),'source_attrs':attrs}
  if iou<.85:
   excluded.append(row)
   print('EXCLUDED_LOW_IOU',c,round(iou,4),flush=True)
   continue
  m=~invalid
  if m.mean()<.01:raise ValueError((c,float(m.mean())))
  buf=io.BytesIO(); np.savez(buf,height=h.astype(np.float16),speed=np.where(m,sp,0).astype(np.float16),mask=m)
  z.writestr(c+'.npz',buf.getvalue());row['valid_fraction']=float(m.mean());rows.append(row)
  if (i+1)%25==0:print('V5_PROCESSED',i+1,'included',len(rows),'excluded',len(excluded),'bytes',archive.stat().st_size,flush=True)
sha=hashlib.sha256()
with archive.open('rb') as f:
 for block in iter(lambda:f.read(4*1024*1024),b''):sha.update(block)
manifest.write_text(json.dumps({'source':str(src),'requested':len(ids),'n':len(rows),'excluded':excluded,'cases':rows,'archive_bytes':archive.stat().st_size,'sha256':sha.hexdigest(),'min_iou':.85,'mask_source':'Uped invalid pixels'},indent=2,default=str))
print('V5_COMPLETE',len(rows),'excluded',len(excluded),archive.stat().st_size,sha.hexdigest(),flush=True)
