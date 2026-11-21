"""Isolated L0f smoke; old outputs remain untouched."""
import json, os, sys, time, traceback
from pathlib import Path
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0/L0f')
OUT=ROOT/'smoke_v2'/'out'
OUT.mkdir(parents=True,exist_ok=False)
import torch, torch_geometric
print('TORCH_DIAGNOSTIC',json.dumps({'torch':torch.__version__,'torch_cuda':torch.version.cuda,'pyg':torch_geometric.__version__,'available':torch.cuda.is_available(),'count':torch.cuda.device_count(),'name':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,'visible':os.getenv('CUDA_VISIBLE_DEVICES'),'job':os.getenv('JOB_ID') or os.getenv('SGE_JOB_ID')}),flush=True)
if not (os.getenv('JOB_ID') or os.getenv('SGE_JOB_ID')): raise RuntimeError('not in UGE job')
if not torch.cuda.is_available(): raise RuntimeError('CUDA unavailable')
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT.parent))
import l0b_worker as worker
from l0f_compat_v2 import apply as apply_compat
print('COMPAT_CLASSES',apply_compat(),flush=True)
worker.ROOT=ROOT
worker.OUT=OUT
import numpy as np
from scipy.sparse.linalg import cg
from l0b_generate import make_sample

def run():
    result={'status':'in_progress','gpu':torch.cuda.get_device_name(0),'job_id':os.getenv('JOB_ID') or os.getenv('SGE_JOB_ID'),'samples':[],'cg':[]}
    model=worker.model_new().to('cuda:0')
    optimizer=torch.optim.AdamW(model.parameters())
    for kind in range(3):
        for index in range(2):
            seed=110000+kind+3*index
            A,b,meta=make_sample(seed,kind)
            result['samples'].append(meta)
            data=worker.graph(A,b,'cuda:0')
            start=time.perf_counter()
            val=worker.forward_backward(model,data,optimizer)
            torch.cuda.synchronize()
            result['samples'][-1].update(loss=val,training_step_seconds=time.perf_counter()-start)
            if index==0 and kind<2:
                its=[0]
                _,info=cg(A,b,rtol=1e-6,atol=0,maxiter=1000,callback=lambda _:its.__setitem__(0,its[0]+1))
                result['cg'].append({'geometry':kind,'iterations':its[0],'info':int(info)})
            del data,A,b
            print('SMOKE_SAMPLE',json.dumps(result['samples'][-1]),flush=True)
    result['probe']=worker.probe(model,'cuda:0')
    result['status']='ok' if result['probe']['status']=='ok' and all(v['info']==0 for v in result['cg']) else 'gate_stopped'
    return result
if __name__=='__main__':
    t=time.perf_counter()
    try: result=run()
    except Exception as exc: result={'status':'error','error':repr(exc),'traceback':traceback.format_exc()[-4000:]}
    result['wall_seconds']=time.perf_counter()-t
    with (OUT/'smoke.json').open('x') as f: json.dump(result,f,indent=2,allow_nan=False)
    print('SMOKE_RESULT',json.dumps(result),flush=True)
    if result['status']!='ok': raise SystemExit(2)
