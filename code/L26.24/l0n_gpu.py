"""L26.24 L0b bounded NeuralIF training/probe on an allocated A10 only.
Data protocol: l0b_generate.py and frozen L0b_参数来源表.md.
This is NOT author-original data; no external checkpoints or pickle.
"""
import gc, json, os, sys, time, types, traceback
from pathlib import Path
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0/L0n')
OUT=ROOT/'gpu'/'out'
OUT.mkdir(parents=True,exist_ok=True)
# The model's training path does not invoke numml; only its unmodified
# inference branch uses it. Force the training/eval sparse-torch path.
numml=types.ModuleType('numml'); sparse=types.ModuleType('numml.sparse')
numml.sparse=sparse; sys.modules['numml']=numml; sys.modules['numml.sparse']=sparse
sys.path[:0]=[str(ROOT),str(ROOT.parent/'repo'),str(ROOT.parent/'L0m/vendor'),str(ROOT.parent/'L0m')]
import numpy as np
import torch
from scipy.io import mmread
from scipy.sparse.linalg import cg, LinearOperator, spsolve_triangular
from torch_geometric.data import Data
from neuralif.models import NeuralIF
from l0i_compat import apply as apply_compat
print("COMPAT_CLASSES",apply_compat(),flush=True)
from l0i_sparse_loss import hutchinson_eq7 as loss
from l0n_generate_v2 import make_sample
SEED_TABLE=json.loads((ROOT/'accepted_seeds.json').read_text())
assert SEED_TABLE['status']=='complete' and len(SEED_TABLE['accepted'])==1065
SPLIT_ROWS={key:[r for r in SEED_TABLE['accepted'] if r['split']==key] for key in ('train','val','test')}
assert [len(SPLIT_ROWS[k]) for k in ('train','val','test')]==[750,15,300]
def sample_spec(split,index):
    row=SPLIT_ROWS[split][index]
    return row['seed'],row['geometry']

def save(filename,data):
    p=OUT/filename
    with p.open('x') as f: json.dump(data,f,indent=2,allow_nan=False)

def graph(A,b,device):
    A=A.tocoo()
    edges=np.stack((A.row,A.col)).astype(np.int64,copy=False)
    return Data(x=torch.from_numpy(np.asarray(b,dtype=np.float32).copy()).view(-1,1).to(device),
                edge_index=torch.from_numpy(edges.copy()).to(device),
                edge_attr=torch.from_numpy(A.data.astype(np.float32,copy=True)).view(-1,1).to(device))

def model_new():
    return NeuralIF(latent_size=8,message_passing_steps=3,skip_connections=True,
                    augment_nodes=True,global_features=0,decode_nodes=False,
                    normalize_diag=False,activation='relu',aggregate=None,
                    graph_norm=False,two_hop=False,edge_features=1,normalize=False)

def forward_backward(model,data,optim=None):
    output,_,_=model(data)
    objective=loss(output,data)
    if optim is not None:
        if not torch.isfinite(objective).item(): raise FloatingPointError('nonfinite loss')
        objective.backward()
        if any(not torch.isfinite(p.grad).all().item() for p in model.parameters() if p.grad is not None): raise FloatingPointError('nonfinite gradient')
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
        optim.step(); optim.zero_grad(set_to_none=True)
        if any(not torch.isfinite(p).all().item() for p in model.parameters()):
            raise FloatingPointError('nonfinite parameter after optimizer step')
    return float(objective.detach())

def probe(model,device):
    folder=sorted(Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_D1b/segments/later/Solving').glob('PresCorr-*'))[0]
    result={'source':str(folder),'status':'not_started','n':None,'nnz':None,
            'forward_seconds':None,'backward_seconds':None,'gpu_peak_bytes':None,
            'gpu_total_bytes':torch.cuda.get_device_properties(0).total_memory}
    t=time.perf_counter()
    try:
        A=-mmread(str(folder/'A.mtx.gz')).tocsr(); A.sum_duplicates()
        b=-np.load(folder/'b.npy'); result.update(n=A.shape[0],nnz=A.nnz)
        data=graph(A,b,device); del A,b
        torch.cuda.reset_peak_memory_stats()
        model.train(); model.zero_grad(set_to_none=True)
        torch.cuda.synchronize(); start=time.perf_counter()
        output,_,_=model(data)
        torch.cuda.synchronize(); result['forward_seconds']=time.perf_counter()-start
        objective=loss(output,data)
        torch.cuda.synchronize(); start=time.perf_counter()
        objective.backward()
        torch.cuda.synchronize(); result['backward_seconds']=time.perf_counter()-start
        result['status']='ok'; result['gpu_peak_bytes']=torch.cuda.max_memory_allocated()
    except (torch.cuda.OutOfMemoryError, RuntimeError, MemoryError) as e:
        result['status']='oom_or_runtime_error'; result['error']=str(e)[-1000:]
        result['gpu_peak_bytes']=torch.cuda.max_memory_allocated()
    finally:
        result['total_seconds']=time.perf_counter()-t
        for k in ('data','output','objective'):
            if k in locals(): del locals()[k]
        model.zero_grad(set_to_none=True)
        gc.collect(); torch.cuda.empty_cache()
        save('l0b_memprobe.json',result)
    return result

def main():
    assert (os.environ.get('JOB_ID') or os.environ.get('SGE_JOB_ID')), 'Must run on UGE worker'
    assert torch.cuda.is_available(), 'A10 GPU not allocated'
    assert os.getenv('CUDA_VISIBLE_DEVICES'), 'Scheduler GPU binding absent'
    assert os.getenv('OMP_NUM_THREADS')=='1'
    device='cuda:0'; torch.manual_seed(42); np.random.seed(42)
    print('device',torch.cuda.get_device_name(0),'CVD',os.getenv('CUDA_VISIBLE_DEVICES'),flush=True)
    model=model_new().to(device)
    print('trainable_parameters',sum(p.numel() for p in model.parameters()),flush=True)
    probe_result=probe(model,device)
    report={'status':'not_run','selfcheck':'不判','reason':None,
            'neuralif_mean_iterations':None,'ic0_mean_iterations':None,
            'neuralif_over_ic0_ratio':None,'neuralif_in_134_202':None,
            'train_wall_seconds':None,'none_mean_iterations':None,'test_summary':None,'none_reference_iterations':856.38,'train_samples':750,'validation_samples':15,
            'test_samples':300,'epochs_target':50,'epochs_completed':0,'epoch_losses':[],'nonfinite':[],
            'probe_status':probe_result['status'],'gpu_peak_bytes':probe_result['gpu_peak_bytes'],
            'gpu_model':torch.cuda.get_device_name(0),'versions':{'torch':torch.__version__}}
    if probe_result['status']!='ok':
        report['reason']='full-size forward/backward probe failed; no training attempted'
        save('l0b_selfcheck.json',report); return
    # Deterministic frozen seed table; generate each CSR once on 2 CPU slots.
    # Never transfer all graphs to GPU: the CSR cache lives in host RAM only.
    from concurrent.futures import ThreadPoolExecutor
    from scipy.sparse import csr_matrix
    import resource
    def generate(row):
        A,b,meta=make_sample(row['seed'],row['geometry'])
        A=A.tocsr(); A.sum_duplicates(); A.sort_indices()
        A.data=np.ascontiguousarray(A.data,dtype=np.float64)
        A.indices=np.ascontiguousarray(A.indices,dtype=np.int32)
        A.indptr=np.ascontiguousarray(A.indptr,dtype=np.int32)
        b=np.ascontiguousarray(b,dtype=np.float64)
        assert (A.shape[0],A.nnz)==(row['n'],row['nnz'])
        return A,b,meta
    gen_start=time.perf_counter()
    cache={}
    host_bytes=0
    with ThreadPoolExecutor(max_workers=2) as executor:
        for split in ('train','val','test'):
            cache[split]=[]
            for j,item in enumerate(executor.map(generate,SPLIT_ROWS[split])):
                A,b,meta=item
                host_bytes+=A.data.nbytes+A.indices.nbytes+A.indptr.nbytes+b.nbytes
                cache[split].append(item)
                if (j+1)%100==0:
                    print('cache',split,j+1,'seconds',time.perf_counter()-gen_start,'rss_kib',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,flush=True)
                if host_bytes>8_000_000_000:
                    report.update(status='budget_gate_stopped',reason='host CSR cache exceeded 8 GB',host_cache_bytes=host_bytes)
                    save('l0b_selfcheck.json',report); return
    report['host_cache_bytes']=host_bytes
    report['generation_wall_seconds']=time.perf_counter()-gen_start
    report['host_peak_rss_kib_after_generation']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    optimizer=torch.optim.AdamW(model.parameters())
    started=time.perf_counter()
    for epoch in range(50):
        epoch_start=time.perf_counter()
        epoch_losses=[]
        for i in np.random.default_rng(42+epoch).permutation(750):
            A,b,_=cache['train'][int(i)]
            data=graph(A,b,device)
            try: epoch_losses.append(forward_backward(model,data,optimizer))
            except FloatingPointError as e:
                report['nonfinite'].append({'epoch':epoch+1,'train_index':int(i),'seed':SPLIT_ROWS['train'][int(i)]['seed'],'error':str(e)})
                report.update(status='nonfinite_stopped',reason=str(e),train_wall_seconds=time.perf_counter()-started)
                save('l0b_selfcheck.json',report); return
            del data
        torch.cuda.synchronize()
        epoch_seconds=time.perf_counter()-epoch_start
        model.eval(); val_losses=[]
        with torch.no_grad():
            for A_val,b_val,_ in cache['val']:
                d=graph(A_val,b_val,device); L_val,_,_=model(d); v=loss(L_val,d)
                if not torch.isfinite(v).item():
                    report['nonfinite'].append({'epoch':epoch+1,'split':'val','error':'nonfinite loss'})
                    report.update(status='nonfinite_stopped',reason='nonfinite validation loss')
                    save('l0b_selfcheck.json',report); return
                val_losses.append(float(v));del d,L_val,v
        model.train()
        report['epoch_losses'].append({'epoch':epoch+1,'train_mean':float(np.mean(epoch_losses)),'val_mean':float(np.mean(val_losses))})
        print('LOSSES',report['epoch_losses'][-1],flush=True)
        report['epochs_completed']=epoch+1
        print('epoch',epoch+1,'seconds',epoch_seconds,'elapsed',time.perf_counter()-started,flush=True)
        if epoch==0:
            report['epoch1_wall_seconds']=epoch_seconds
            # Includes complete generation once, 50 measured-epoch extrapolation,
            # and conservative bounded evaluation allowance; stop before overrun.
            estimate=report['generation_wall_seconds']+50*epoch_seconds+3600
            report['estimated_total_seconds']=estimate
            report['estimate_evaluation_allowance_seconds']=3600
            if estimate>1.80*3600:
                report.update(status='budget_gate_stopped',reason='full 50 epochs plus generation and evaluation allowance exceed h_rt',train_wall_seconds=time.perf_counter()-started)
                save('l0b_selfcheck.json',report); return
        if time.perf_counter()-gen_start>1.60*3600:
            report.update(status='budget_gate_stopped',reason='elapsed full-job time budget before completion',train_wall_seconds=time.perf_counter()-started)
            save('l0b_selfcheck.json',report); return
    report['train_wall_seconds']=time.perf_counter()-started
    report['gpu_peak_bytes']=max(report['gpu_peak_bytes'] or 0,torch.cuda.max_memory_allocated())
    # Training checkpoint is this run's own; never load external weights.
    torch.save(model.cpu().state_dict(),OUT/'own_model.pt')
    model.to(device).eval()
    # Validate on all 15 cases before opening the 300-case test split.
    # Evaluation applies the same normal-equation CG relative residual to both.
    import ctypes as C
    from scipy.sparse import tril, csr_matrix
    lib=C.CDLL('/groups/kareem/[用户]/L26_24_LINSYS_20261115_B/libic0_B2.so')
    I=np.ctypeslib.ndpointer(dtype=np.int32,flags='C_CONTIGUOUS')
    D=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
    lib.ic0_factor.argtypes=[C.c_int,I,I,D,D]; lib.ic0_factor.restype=C.c_int
    for split,count in [('val',15),('test',300)]:
        rows=[]
        for i in range(count):
            A,b,meta=cache[split][i]
            data=graph(A,b,device)
            # Do not enter torch.inference_mode; that would invoke the
            # uninstalled numml C++ extension. Model weights/architecture stay identical.
            with torch.no_grad():
                L,_,_=model(data)
            L=L.coalesce().cpu(); ij=L.indices().numpy(); values=L.values().numpy()
            lower=csr_matrix((values,(ij[0],ij[1])),shape=A.shape).astype(np.float64)
            lower.sum_duplicates(); lower.sort_indices(); del L,data
            if not np.all(np.isfinite(lower.data)):
                report['nonfinite'].append({'split':split,'index':i,'seed':SPLIT_ROWS[split][i]['seed'],'field':'factor','count':int(np.sum(~np.isfinite(lower.data)))})
                report.update(status='nonfinite_stopped',reason='learned factor nonfinite')
                save('l0b_selfcheck.json',report); return
            def precond(x,mat):
                return spsolve_triangular(mat.T.tocsr(),spsolve_triangular(mat,x,lower=True),lower=False)
            try:
                M=LinearOperator(A.shape,matvec=lambda v:precond(v,lower),dtype=np.float64)
                ni=[0]
                x,info=cg(A,b,rtol=1e-6,atol=0,maxiter=10000,M=M,callback=lambda _:ni.__setitem__(0,ni[0]+1))
                neuralits=ni[0] if info==0 else None
            except Exception as e:
                neuralits=None; print('neural_solver_error',i,str(e),flush=True)
            lower_ic=tril(A,format='csr');lower_ic.sort_indices()
            fact=np.empty_like(lower_ic.data)
            breakdown=lib.ic0_factor(A.shape[0],lower_ic.indptr,lower_ic.indices,
                                     np.ascontiguousarray(lower_ic.data),fact)
            icits=None
            if breakdown==0:
                lower_ic.data=fact
                try:
                    M=LinearOperator(A.shape,matvec=lambda v:precond(v,lower_ic),dtype=np.float64)
                    ci=[0]
                    x,info=cg(A,b,rtol=1e-6,atol=0,maxiter=10000,M=M,callback=lambda _:ci.__setitem__(0,ci[0]+1))
                    icits=ci[0] if info==0 else None
                except Exception as e: print('ic_solver_error',i,str(e),flush=True)
            un=[0]
            _,uninfo=cg(A,b,rtol=1e-6,atol=0,maxiter=10000,callback=lambda _:un.__setitem__(0,un[0]+1))
            noneits=un[0] if uninfo==0 else None
            rows.append({'index':i,'n':meta['n'],'nnz':meta['nnz'],'neural_iterations':neuralits,
                         'ic0_iterations':icits,'ic_breakdown_row':int(breakdown),'none_iterations':noneits})
            del lower,lower_ic,M
            if (i+1)%10==0: print('eval',split,i+1,'elapsed',time.perf_counter()-started,flush=True)
            if time.perf_counter()-gen_start>1.75*3600:
                report.update(status='budget_gate_stopped',reason='evaluation incomplete within GPU allocation',evaluated={split:len(rows)},train_wall_seconds=report['train_wall_seconds'])
                save('l0b_selfcheck.json',report);return
        report[split+'_rows']=rows
    test=report['test_rows']; report['test_summary']={key:{'converged':sum(r[col] is not None for r in test),'median_converged_only':float(np.median([r[col] for r in test if r[col] is not None])) if any(r[col] is not None for r in test) else None} for key,col in [('neuralif','neural_iterations'),('ic0','ic0_iterations'),('none','none_iterations')]}
    nits=[r['neural_iterations'] for r in test]; icits=[r['ic0_iterations'] for r in test]
    noits=[r['none_iterations'] for r in test]
    report['none_mean_iterations']=float(np.mean(noits)) if None not in noits else None
    report['ic0_mean_iterations']=float(np.mean(icits)) if None not in icits else None
    report['neuralif_mean_iterations']=float(np.mean(nits)) if None not in nits else None
    report['neuralif_over_ic0_ratio']=(report['neuralif_mean_iterations']/report['ic0_mean_iterations']
        if report['neuralif_mean_iterations'] is not None and report['ic0_mean_iterations'] is not None else None)
    in_ic=(report['ic0_mean_iterations'] is not None and 166.05*.8<=report['ic0_mean_iterations']<=166.05*1.2)
    report['neuralif_in_134_202']=(134<=report['neuralif_mean_iterations']<=202 if report['neuralif_mean_iterations'] is not None else None)
    if None in nits or None in icits:
        report.update(status='evaluation_incomplete',reason='one or more solvers failed; cannot infer missing solver mean',selfcheck='不判')
    else:
        report.update(status='complete',
                      selfcheck=('不判' if not in_ic else '过' if report['neuralif_in_134_202'] else '不过'),
                      reason=('reconstructed IC0 distribution differs from original' if not in_ic else None))
    save('l0b_selfcheck.json',report)

if __name__=='__main__':
    try: main()
    except BaseException as e:
        if not (OUT/'l0b_selfcheck.json').exists():
            save('l0b_selfcheck.json',{'status':'error','selfcheck':'不判','error':str(e),'traceback':traceback.format_exc()[-4000:]})
        raise
