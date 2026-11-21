#!/usr/bin/env python3
"""Delay-6 FuXi-CFD station inference, pinned M7 physics and normalized inputs."""
import hashlib,json,math,os,time,traceback
from pathlib import Path
import numpy as np
import onnxruntime as ort
from scipy.ndimage import zoom
import sys
sys.path.insert(0,'/content/m7')
import full_m7 as m
R=Path('/content/delay6');O=R/'infer';O.mkdir(parents=True,exist_ok=True)

def run():
 start=time.monotonic()
 istats=np.load(m.ROOT/'inference_example/normalization/scaler_input.npy',allow_pickle=True).item()
 ostats=np.load(m.ROOT/'inference_example/normalization/scaler_output.npy',allow_pickle=True).item()
 model=m.ROOT/'model/fuxicfd_model.onnx'
 with model.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
 assert sha=='13daae67371d20a7ffb00db0a6c4679e580c28e77d2521eb7c2dcf9e80f20b3e'
 sess=ort.InferenceSession(str(model),providers=['CUDAExecutionProvider','CPUExecutionProvider'])
 assert sess.get_providers()[0]=='CUDAExecutionProvider'
 stat={}
 for s in m.SITES:
  d=m.dem(s);rough=np.full_like(d,.01)
  a=np.stack([(d-istats['high_mean'][0])/istats['high_std'][0],(rough-istats['high_mean'][1])/istats['high_std'][1]])
  stat[s['site']]=zoom(a,(1,300/301,300/301),order=1).astype('float32')
 print('INFER_SETUP',sha,'sites',len(stat),'sec',time.monotonic()-start,flush=True)
 files=sorted((R/'gfs').glob('*.npz'))
 assert files
 done=0
 for n,p in enumerate(files,1):
  out=O/(p.stem+'.jsonl')
  if out.exists():continue
  d=np.load(p,allow_pickle=True);rows=d['rows'];uv=d['uv'];assert len(rows)==len(uv)
  tmp=out.with_suffix('.partial')
  with tmp.open('x') as f:
   for row,grid in zip(rows,uv):
    site,init,fhr,new,raw,v1,zsurf,dz=row
    x=(grid-istats['low_mean'][:,None,None])/istats['low_std'][:,None,None]
    x=np.concatenate([zoom(x,(1,300/9,300/9),order=1).astype('float32'),stat[site]])[None]
    t=time.monotonic();pred=sess.run(None,{sess.get_inputs()[0].name:x})[0];secs=time.monotonic()-t
    assert pred.shape==(1,27,4,300,300)
    u=pred[0,1,0,149,149]*ostats['std'][1,0]+ostats['mean'][1,0]
    v=pred[0,1,1,149,149]*ostats['std'][1,1]+ostats['mean'][1,1]
    f.write(json.dumps({'site':site,'init_new':init,'fhr':int(fhr),'source_fhr':int(new),'raw':float(raw),'v1':float(v1),'z_model_sfc':float(zsurf),'dz':float(dz),'fx':float(math.hypot(u,v)),'infer_sec':secs})+'\n')
  tmp.rename(out);done+=len(rows)
  if n%12==0:print('INFER_PROGRESS',n,len(files),'new_rows',done,'wall',round(time.monotonic()-start,1),flush=True)
 print('INFER_DONE',len(files),done,round(time.monotonic()-start,1),flush=True)
if __name__=='__main__':
 try:run()
 except Exception:
  (R/'infer.failed').write_text(traceback.format_exc());raise
