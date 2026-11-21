"""L1d: per-system positive scalar normalization, 50 epochs, one-system factor gate."""
import gc, json, os, sys, time, traceback, resource
from pathlib import Path
import numpy as np
import torch
from scipy.sparse import csr_matrix, save_npz
sys.path.insert(0, str(Path(__file__).resolve().parent))
import l1_gpu as prior
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/L1d')
OUT=ROOT/'gpu'/'out'

def scaling(A):
    diag=A.diagonal()
    assert np.isfinite(diag).all() and (diag>0).all()
    return 1.0/float(np.mean(diag))

def infer(model,d,device,save=True,destination=OUT):
    A,b=prior.load(d);s=scaling(A);data=prior.graph(A*s,b*s,device)
    with torch.no_grad():
        for _ in range(2):
            f,_,_=model(data);torch.cuda.synchronize();del f
        times=[];first=None;diffs=[]
        for rep in range(5):
            torch.cuda.synchronize();t=time.perf_counter()
            f,_,_=model(data);torch.cuda.synchronize();f=f.coalesce().cpu()
            ij=f.indices().numpy(); vals=f.values().numpy()
            candidate=csr_matrix((vals,(ij[0],ij[1])),shape=A.shape).astype(np.float64)
            candidate.sum_duplicates();candidate.sort_indices()
            assert np.isfinite(candidate.data).all() and (candidate.diagonal()>0).all()
            times.append(time.perf_counter()-t)
            if first is None: first=candidate;diffs.append({'rep':rep,'nnz':int(candidate.nnz),'max_relative_difference':0.0})
            else:
                delta=candidate-first
                rel=float(np.max(np.abs(delta.data))/np.max(np.abs(first.data))) if delta.nnz else 0.0
                diffs.append({'rep':rep,'nnz':int(candidate.nnz),'max_relative_difference':rel})
                assert candidate.nnz==first.nnz and rel<=1e-4,(d.name,rep,rel)
            del f,candidate
    entry={'system':d.name,'source':str(d),'scale':s,'diag_min':float(A.diagonal().min()),'diag_mean':1/s,'diag_max':float(A.diagonal().max()),'inference_seconds_reps':times,'factor_nnz':int(first.nnz),'repeat_differences':diffs}
    if save:
        dest=destination/(d.name+'.npz');assert not dest.exists();save_npz(dest,first,compressed=True)
        entry.update(factor_file=dest.name,factor_bytes=dest.stat().st_size)
    del A,b,data;gc.collect();torch.cuda.empty_cache()
    return entry

def main(dry=False):
    print('COMPAT',prior.apply_compat(),flush=True)
    if dry:
        from scipy.sparse import diags
        A=diags([-np.ones(2047),4*np.ones(2048),-np.ones(2047)],[-1,0,1],format='csr');s=scaling(A)
        model=prior.model_new(); opt=torch.optim.AdamW(model.parameters());data=prior.graph(A*s,np.ones(2048)*s,'cpu')
        factor,_,_=model(data);v=prior.loss(factor,data);assert torch.isfinite(v).item();v.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);opt.step()
        print('L1D_DRY_PASS',s,float(v),flush=True);return
    assert os.environ.get('JOB_ID') or os.environ.get('SGE_JOB_ID')
    assert torch.cuda.is_available() and torch.cuda.device_count()==1
    assert all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
    OUT.mkdir(parents=True,exist_ok=False)
    torch.manual_seed(42);np.random.seed(42);torch.cuda.reset_peak_memory_stats()
    train=[('t0',d) for d in prior.items('t0')]+[('restart',d) for d in prior.items('restart')]
    assert len(train)==40 and len(prior.items('later'))==20
    report={'status':'running','epochs_target':50,'epoch_losses':[],'nonfinite':[],'scales':[],'factors':[],'gpu_model':torch.cuda.get_device_name(0)}
    model=prior.model_new().cuda();optimizer=torch.optim.AdamW(model.parameters())
    cache=[];t=time.perf_counter()
    for seg,d in train:
        A,b=prior.load(d);s=scaling(A)
        report['scales'].append({'segment':seg,'system':d.name,'scale':s,'diag_min':float(A.diagonal().min()),'diag_mean':1/s,'diag_max':float(A.diagonal().max())})
        cache.append((d,A,b,s))
    report['host_csr_bytes']=sum(A.data.nbytes+A.indices.nbytes+A.indptr.nbytes+b.nbytes for _,A,b,_ in cache)
    report['host_peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report['generation_seconds']=time.perf_counter()-t
    print('CACHE',report['host_csr_bytes'],'RSS',report['host_peak_rss_kib'],flush=True)
    start=time.perf_counter()
    for epoch in range(50):
        t=time.perf_counter(); model.train(); values=[]
        for j in np.random.default_rng(42+epoch).permutation(len(cache)):
            d,A,b,s=cache[int(j)];data=prior.graph(A*s,b*s,'cuda:0')
            try:
                factor,_,_=model(data);v=prior.loss(factor,data)
                if not torch.isfinite(v).item():raise FloatingPointError('loss')
                v.backward()
                if any(not torch.isfinite(p.grad).all().item() for p in model.parameters() if p.grad is not None):raise FloatingPointError('gradient')
                torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);optimizer.step();optimizer.zero_grad(set_to_none=True)
                if any(not torch.isfinite(p).all().item() for p in model.parameters()):raise FloatingPointError('parameter')
                values.append(float(v.detach()))
            except (FloatingPointError,torch.cuda.OutOfMemoryError) as exc:
                report['nonfinite'].append({'epoch':epoch+1,'system':d.name,'error':str(exc)})
                report.update(status='nonfinite_stopped',epochs_completed=epoch)
                prior.write_new(OUT/'l1d_train.json',report);return
            del data,factor,v
        torch.cuda.synchronize();row={'epoch':epoch+1,'train_mean':float(np.mean(values)),'epoch_seconds':time.perf_counter()-t}
        report['epoch_losses'].append(row);print('EPOCH',json.dumps(row),flush=True)
        if epoch==0:
            report['epoch1_seconds']=row['epoch_seconds']
            report['estimated_total_seconds']=report['generation_seconds']+50*row['epoch_seconds']+600
            if report['estimated_total_seconds']>6500:
                report.update(status='budget_gate_stopped');prior.write_new(OUT/'l1d_train.json',report);return
    report['train_wall_seconds']=time.perf_counter()-start;report['epochs_completed']=50
    torch.save(model.cpu().state_dict(),OUT/'own_model.pt');model.cuda().eval()
    # Only the first held-out system is exported until the CPU gate passes.
    first=prior.items('later')[0];entry=infer(model,first,'cuda:0');report['factors'].append(entry)
    report.update(status='single_factor_ready',gpu_peak_bytes=torch.cuda.max_memory_allocated())
    prior.write_new(OUT/'l1d_train.json',report)
    print('L1D_SINGLE_READY',json.dumps(entry),flush=True)
if __name__=='__main__':
    try: main('--dry-run' in sys.argv)
    except BaseException:
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'error.txt').write_text(traceback.format_exc());raise
