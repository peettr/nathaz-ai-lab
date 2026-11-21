"""L26.24 L1, train-only system graphs and held-out GPU factors on CRC."""
import argparse, gc, json, os, re, sys, time, types, traceback, resource
from pathlib import Path
import numpy as np
import torch
from scipy.io import mmread
from scipy.sparse import save_npz, csr_matrix
from torch_geometric.data import Data
BASE=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1')
L0=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0')
SOURCES={'t0':Path('/groups/kareem/[用户]/L26_24_LINSYS_20261114/Solving'),'restart':Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_D1/segments/restart/Solving'),'later':Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_D1b/segments/later/Solving')}
# Training and evaluation branches do not invoke optional numml C++ extension.
n=types.ModuleType('numml'); s=types.ModuleType('numml.sparse'); n.sparse=s;sys.modules['numml']=n;sys.modules['numml.sparse']=s
sys.path[:0]=[str(L0/'repo'),str(L0/'L0i'),str(BASE/'gpu')]
from neuralif.models import NeuralIF
from l0i_compat import apply as apply_compat
from l0i_sparse_loss import hutchinson_eq7 as loss

def items(seg):
    dirs=sorted(SOURCES[seg].glob('PresCorr-*'),key=lambda d:tuple(map(int,re.findall(r'\d+',d.name))))
    assert len(dirs)==20,(seg,len(dirs))
    return dirs

def model_new():
    return NeuralIF(latent_size=8,message_passing_steps=3,skip_connections=True,augment_nodes=True,global_features=0,decode_nodes=False,normalize_diag=False,activation='relu',aggregate=None,graph_norm=False,two_hop=False,edge_features=1,normalize=False)

def load(d):
    A=-mmread(str(d/'A.mtx.gz')).tocsr().astype(np.float64)
    A.sum_duplicates();A.sort_indices()
    assert A.shape[0]==1144164 and np.all(A.diagonal()>0)
    b=-np.load(d/'b.npy').astype(np.float64)
    return A,b

def graph(A,b,device):
    C=A.tocoo(); edges=np.stack((C.row,C.col)).astype(np.int64)
    return Data(x=torch.from_numpy(np.asarray(b,dtype=np.float32).copy()).view(-1,1).to(device),edge_index=torch.from_numpy(edges.copy()).to(device),edge_attr=torch.from_numpy(C.data.astype(np.float32,copy=True)).view(-1,1).to(device))

def write_new(path,obj):
    with path.open('x') as f:json.dump(obj,f,indent=2,allow_nan=False)

def main(dry_run=False):
    affected=apply_compat(); print('COMPAT',affected,flush=True)
    train=[('t0',d) for d in items('t0')]+[('restart',d) for d in items('restart')]
    test=items('later')
    assert set(str(d) for _,d in train).isdisjoint(str(d) for d in test)
    assert os.environ.get('OMP_NUM_THREADS')=='1'
    if dry_run:
        from scipy.sparse import diags
        A=diags([-np.ones(2047),4*np.ones(2048),-np.ones(2047)],[-1,0,1],format='csr')
        m=model_new();opt=torch.optim.AdamW(m.parameters()); torch.manual_seed(42)
        data=graph(A,np.ones(2048),'cpu');out,_,_=m(data);v=loss(out,data)
        assert torch.isfinite(v).item();v.backward();torch.nn.utils.clip_grad_norm_(m.parameters(),1.0);opt.step()
        assert all(torch.isfinite(p).all().item() for p in m.parameters())
        print('L1_DRYRUN_PASS',len(train),len(test),float(v),flush=True);return
    assert os.getenv('JOB_ID') or os.getenv('SGE_JOB_ID')
    assert torch.cuda.is_available() and torch.cuda.device_count()==1
    device='cuda:0';torch.manual_seed(42);np.random.seed(42)
    outdir=BASE/'gpu'/'out'; outdir.mkdir(exist_ok=True)
    report={'status':'running','source':'D0/D1/D1b immutable A.mtx.gz; only t0+restart train','epochs_target':50,'epoch_losses':[],'nonfinite':[],'scaling':None,'factors':[],'gpu_model':torch.cuda.get_device_name(0),'thread_env':{k:os.getenv(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}}
    model=model_new().to(device);optimizer=torch.optim.AdamW(model.parameters())
    # Fixed scalar chosen from the 40 train systems only. Report it and apply identically to held-out graphs.
    cache=[]; t=time.perf_counter(); maxdiag=0.
    for seg,d in train:
        A,b=load(d); cache.append((seg,d,A,b));maxdiag=max(maxdiag,float(np.max(np.abs(A.diagonal()))))
    assert maxdiag>0 and np.isfinite(maxdiag)
    scale=1.0;report['scaling']={'value':scale,'train_max_abs_diag':maxdiag,'reason':'author-default unscaled A; only a separately documented recovery after observed nonfinite may use a common positive scalar'}
    report['host_csr_bytes']=sum(A.data.nbytes+A.indices.nbytes+A.indptr.nbytes+b.nbytes for _,_,A,b in cache)
    report['host_peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report['generation_seconds']=time.perf_counter()-t
    print('CACHE',report['host_csr_bytes'],'SCALE',scale,'RSS',report['host_peak_rss_kib'],flush=True)
    # Probe tiny subset for finite objective before training; avoid changing the frozen 50 epochs.
    begin=time.perf_counter(); torch.cuda.reset_peak_memory_stats()
    for epoch in range(50):
        start=time.perf_counter();model.train();values=[]
        for j in np.random.default_rng(42+epoch).permutation(len(cache)):
            seg,d,A,b=cache[int(j)]; data=graph(A*scale,b*scale,device)
            try:
                factor,_,_=model(data);v=loss(factor,data)
                if not torch.isfinite(v).item():raise FloatingPointError('loss')
                v.backward()
                if any(not torch.isfinite(p.grad).all().item() for p in model.parameters() if p.grad is not None):raise FloatingPointError('gradient')
                torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);optimizer.step();optimizer.zero_grad(set_to_none=True)
                if any(not torch.isfinite(p).all().item() for p in model.parameters()):raise FloatingPointError('parameter')
                values.append(float(v.detach()))
            except (FloatingPointError,torch.cuda.OutOfMemoryError) as exc:
                report['nonfinite'].append({'epoch':epoch+1,'system':str(d),'error':str(exc)})
                report.update(status='nonfinite_stopped',train_wall_seconds=time.perf_counter()-begin,epochs_completed=epoch)
                write_new(outdir/'l1_train.json',report);return
            del data,factor,v
        torch.cuda.synchronize(); row={'epoch':epoch+1,'train_mean':float(np.mean(values)),'epoch_seconds':time.perf_counter()-start}
        report['epoch_losses'].append(row);print('EPOCH',json.dumps(row),flush=True)
        if epoch==0:
            estimate=report['generation_seconds']+50*row['epoch_seconds']+2400
            report['epoch1_seconds']=row['epoch_seconds'];report['estimated_total_seconds']=estimate
            if estimate>6800:
                report.update(status='budget_gate_stopped',reason='epoch1 extrapolation including factor serialization exceeds GPU allocation')
                write_new(outdir/'l1_train.json',report);return
        if time.perf_counter()-begin>5600:
            report.update(status='budget_gate_stopped',reason='elapsed training GPU allocation')
            write_new(outdir/'l1_train.json',report);return
    report['train_wall_seconds']=time.perf_counter()-begin;report['epochs_completed']=50
    torch.save(model.cpu().state_dict(),outdir/'own_model.pt');model.to(device).eval()
    for d in test:
        A,b=load(d); data=graph(A*scale,b*scale,device)
        with torch.no_grad():
            # Warm-up then five separately synchronized inference+CPU CSR conversions.
            for _ in range(2): f,_,_=model(data);torch.cuda.synchronize();del f
            times=[];lower=None
            for rep in range(5):
                torch.cuda.synchronize();t=time.perf_counter();f,_,_=model(data);torch.cuda.synchronize()
                f=f.coalesce().cpu();ij=f.indices().numpy();vals=f.values().numpy()
                candidate=csr_matrix((vals,(ij[0],ij[1])),shape=A.shape).astype(np.float64)
                candidate.sum_duplicates();candidate.sort_indices()
                assert np.all(np.isfinite(candidate.data)) and np.all(candidate.diagonal()>0)
                torch.cuda.synchronize();times.append(time.perf_counter()-t)
                if rep==0: lower=candidate
                else:
                    assert candidate.nnz==lower.nnz and np.allclose(candidate.data,lower.data,rtol=1e-6,atol=1e-10)
                    del candidate
                del f
        name=d.name;dest=outdir/(name+'.npz');assert not dest.exists();save_npz(dest,lower,compressed=True)
        entry={'system':name,'source':str(d),'factor_file':dest.name,'inference_seconds_reps':times,'factor_nnz':int(lower.nnz),'factor_bytes':dest.stat().st_size,'scale':scale}
        report['factors'].append(entry);print('FACTOR',json.dumps(entry),flush=True)
        del A,b,data,lower;gc.collect();torch.cuda.empty_cache()
        if sum(x['factor_bytes'] for x in report['factors'])>1_300_000_000:
            report.update(status='storage_gate_stopped',reason='factor files exceeded 1.3GB reserve');write_new(outdir/'l1_train.json',report);return
    report.update(status='complete',gpu_peak_bytes=torch.cuda.max_memory_allocated())
    write_new(outdir/'l1_train.json',report)

if __name__=='__main__':
    try: main('--dry-run' in sys.argv)
    except BaseException:
        p=BASE/'gpu'/'out'/'l1_error.txt';p.parent.mkdir(exist_ok=True);p.write_text(traceback.format_exc());raise
