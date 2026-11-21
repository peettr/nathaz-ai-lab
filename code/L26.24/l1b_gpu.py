"""L1b: read-only own checkpoint; repeated GPU inference and first-factor export."""
import gc, json, os, sys, time, traceback
from pathlib import Path
import numpy as np
import torch
from scipy.sparse import csr_matrix, save_npz
sys.path.insert(0, str(Path(__file__).resolve().parent))
import l1_gpu as prior

ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/L1b')
OUT=ROOT/'gpu'/'out'
OLD=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/gpu/out/own_model.pt')

def main(dry=False):
    print('COMPAT',prior.apply_compat(),flush=True)
    model=prior.model_new()
    model.load_state_dict(torch.load(OLD,map_location='cpu',weights_only=True))
    model.eval()
    if dry:
        from scipy.sparse import diags
        A=diags([-np.ones(2047),4*np.ones(2048),-np.ones(2047)],[-1,0,1],format='csr')
        with torch.no_grad():
            f,_,_=model(prior.graph(A,np.ones(2048),'cpu'))
        assert f._nnz()>0
        print('L1B_DRY_PASS',f._nnz(),flush=True); return
    assert os.getenv('JOB_ID') or os.getenv('SGE_JOB_ID')
    assert torch.cuda.is_available() and torch.cuda.device_count()==1
    OUT.mkdir(parents=True,exist_ok=False)
    model=model.cuda(); torch.cuda.reset_peak_memory_stats()
    report={'status':'running','checkpoint_sha256':'e212b308b800e5c7fcdbc7f23287dc74085ff3d02f4da9c59f61e3260da42a22',
            'source':'D1b later 20 systems, original immutable matrix and L1 checkpoint','scale':1.0,'factors':[],'nonfinite':[]}
    for d in prior.items('later'):
        A,b=prior.load(d);data=prior.graph(A,b,'cuda:0')
        with torch.no_grad():
            for _ in range(2):
                f,_,_=model(data);torch.cuda.synchronize();del f
            times=[]; first=None; diffs=[]
            for rep in range(5):
                torch.cuda.synchronize(); start=time.perf_counter()
                f,_,_=model(data);torch.cuda.synchronize()
                f=f.coalesce().cpu(); ij=f.indices().numpy();vals=f.values().numpy()
                candidate=csr_matrix((vals,(ij[0],ij[1])),shape=A.shape).astype(np.float64)
                candidate.sum_duplicates();candidate.sort_indices()
                assert np.isfinite(candidate.data).all() and (candidate.diagonal()>0).all()
                times.append(time.perf_counter()-start)
                if first is None: first=candidate; diffs.append({'rep':rep,'nnz':int(candidate.nnz),'max_relative_difference':0.0})
                else:
                    # Compare by sparse subtraction, not raw .data order or sparse insertion order.
                    delta=candidate-first
                    relative=float(np.max(np.abs(delta.data))/np.max(np.abs(first.data))) if delta.nnz else 0.0
                    diffs.append({'rep':rep,'nnz':int(candidate.nnz),'max_relative_difference':relative})
                    if candidate.nnz!=first.nnz or relative>1e-4:
                        report.update(status='repeat_gate_stopped',failed_system=d.name,repeat_differences=diffs)
                        prior.write_new(OUT/'l1b_manifest.json',report);return
                del f,candidate
        dest=OUT/(d.name+'.npz');assert not dest.exists();save_npz(dest,first,compressed=True)
        entry={'system':d.name,'source':str(d),'factor_file':dest.name,'inference_seconds_reps':times,
               'factor_nnz':int(first.nnz),'factor_bytes':dest.stat().st_size,'scale':1.0,'repeat_differences':diffs}
        report['factors'].append(entry);print('FACTOR',json.dumps(entry),flush=True)
        del A,b,data,first;gc.collect();torch.cuda.empty_cache()
        if sum(x['factor_bytes'] for x in report['factors'])>1_300_000_000:
            report.update(status='storage_gate_stopped');prior.write_new(OUT/'l1b_manifest.json',report);return
    report.update(status='complete',gpu_peak_bytes=torch.cuda.max_memory_allocated())
    prior.write_new(OUT/'l1b_manifest.json',report)
if __name__=='__main__':
    try:main('--dry-run' in sys.argv)
    except BaseException:
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'error.txt').write_text(traceback.format_exc());raise
