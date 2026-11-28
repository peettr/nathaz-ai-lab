"""L1d held-out remaining factors after verified first-system gate."""
import json, os, sys, traceback, gc
from pathlib import Path
import numpy as np
import torch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import l1d_gpu as prior
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/L1d')
OUT=ROOT/'infer'/'out'
def run(dry=False):
    print('COMPAT',prior.prior.apply_compat(),flush=True)
    assert prior.scaling(__import__('scipy').sparse.eye(3,format='csr'))==1
    if dry:
        model=prior.prior.model_new();print('L1D_INFER_DRY_PASS',sum(p.numel() for p in model.parameters()),flush=True);return
    gate=json.loads((ROOT/'gate/out/gate.json').read_text());assert gate['pass'] and gate['iterations']<=650
    train=json.loads((ROOT/'gpu/out/l1d_train.json').read_text());assert train['status']=='single_factor_ready'
    assert os.getenv('JOB_ID') or os.getenv('SGE_JOB_ID')
    assert torch.cuda.is_available() and torch.cuda.device_count()==1
    model=prior.prior.model_new()
    model.load_state_dict(torch.load(ROOT/'gpu/out/own_model.pt',map_location='cpu',weights_only=True));model.cuda().eval()
    OUT.mkdir(parents=True,exist_ok=False);torch.cuda.reset_peak_memory_stats()
    report={'status':'running','source_checkpoint':str(ROOT/'gpu/out/own_model.pt'),'factors':[train['factors'][0]],'nonfinite':[]}
    for d in prior.prior.items('later')[1:]:
        entry=prior.infer(model,d,'cuda:0',destination=OUT)
        report['factors'].append(entry);print('FACTOR',json.dumps(entry),flush=True)
        gc.collect();torch.cuda.empty_cache()
        if sum(e.get('factor_bytes',0) for e in report['factors'])>1_300_000_000:raise RuntimeError('storage gate')
    report.update(status='complete',gpu_peak_bytes=torch.cuda.max_memory_allocated())
    with (OUT/'manifest.json').open('x') as f:json.dump(report,f,indent=2,allow_nan=False)
if __name__=='__main__':
    try:run('--dry-run' in sys.argv)
    except BaseException:
        OUT.mkdir(parents=True,exist_ok=True);(OUT/'error.txt').write_text(traceback.format_exc());raise
