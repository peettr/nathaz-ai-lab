"""L26.24 L0b bounded NeuralIF training/probe on an allocated A10 only.
Data protocol: l0b_generate.py and frozen L0b_参数来源表.md.
This is NOT author-original data; no external checkpoints or pickle.
"""
import gc, json, os, sys, time, types, traceback
from pathlib import Path
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0/L0c')
OUT=ROOT/'full'/'out'
OUT.mkdir(parents=True,exist_ok=True)
# The model's training path does not invoke numml; only its unmodified
# inference branch uses it. Force the training/eval sparse-torch path.
numml=types.ModuleType('numml'); sparse=types.ModuleType('numml.sparse')
numml.sparse=sparse; sys.modules['numml']=numml; sys.modules['numml.sparse']=sparse
sys.path.insert(0,str(ROOT.parent/'repo')); sys.path.insert(0,str(ROOT.parent))
import numpy as np
import torch
from scipy.io import mmread
from scipy.sparse.linalg import cg, LinearOperator, spsolve_triangular
from torch_geometric.data import Data
from neuralif.models import NeuralIF
from neuralif.loss import loss
from l0b_generate import make_sample, sample_spec

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
    objective=loss(output,data,config=None)
    if optim is not None:
        objective.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
        optim.step(); optim.zero_grad(set_to_none=True)
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
        objective=loss(output,data,config=None)
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
    assert 'A10' in torch.cuda.get_device_name(0), torch.cuda.get_device_name(0)
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
            'train_wall_seconds':None,'train_samples':750,'validation_samples':15,
            'test_samples':300,'epochs_target':50,'epochs_completed':0,
            'probe_status':probe_result['status'],'gpu_peak_bytes':probe_result['gpu_peak_bytes'],
            'gpu_model':torch.cuda.get_device_name(0),'versions':{'torch':torch.__version__}}
    if probe_result['status']!='ok':
        report['reason']='full-size forward/backward probe failed; no training attempted'
        save('l0b_selfcheck.json',report); return
    # One exact-size sample timed with original NeuralIF model and sketched loss.
    start=time.perf_counter()
    seed,kind=sample_spec('train',0); A,b,meta=make_sample(seed,kind)
    generation_sec=time.perf_counter()-start
    print('generation_probe',meta,generation_sec,flush=True)
    data=graph(A,b,device); del A,b
    optimizer=torch.optim.AdamW(model.parameters()) # original train.py default
    torch.cuda.synchronize(); start=time.perf_counter()
    loss_value=forward_backward(model,data,optimizer)
    torch.cuda.synchronize(); step_sec=time.perf_counter()-start
    report.update(generation_probe_seconds=generation_sec,step_probe_seconds=step_sec,
                  training_probe_loss=loss_value,training_probe_meta=meta)
    # Full protocol 750 * 50 plus validation/test overhead. Reject if the
    # measured ONE-sample optimistic lower bound already exceeds allocation.
    lower_bound=(generation_sec+step_sec)*750*50
    report['optimistic_lower_bound_seconds']=lower_bound
    if lower_bound>3.5*3600:
        report['reason']='single-sample optimistic full-training lower bound exceeds GPU budget; frozen sample/epoch counts cannot be reduced'
        report['status']='budget_gate_stopped'
        save('l0b_selfcheck.json',report); return
    # Full protocol only if budget gate permits. Generator is deterministic.
    started=time.perf_counter()
    for epoch in range(50):
        for i in np.random.default_rng(42+epoch).permutation(750):
            seed,kind=sample_spec('train',int(i)); A,b,_=make_sample(seed,kind)
            data=graph(A,b,device); del A,b
            forward_backward(model,data,optimizer)
            del data
            if time.perf_counter()-started>3.2*3600:
                report.update(status='budget_gate_stopped',reason='elapsed GPU budget before full protocol',epochs_completed=epoch,train_wall_seconds=time.perf_counter()-started)
                save('l0b_selfcheck.json',report); return
        report['epochs_completed']=epoch+1
        print('epoch',epoch+1,'elapsed',time.perf_counter()-started,flush=True)
    report['train_wall_seconds']=time.perf_counter()-started
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
            seed,kind=sample_spec(split,i); A,b,meta=make_sample(seed,kind)
            data=graph(A,b,device)
            # Do not enter torch.inference_mode; that would invoke the
            # uninstalled numml C++ extension. Model weights/architecture stay identical.
            with torch.no_grad():
                L,_,_=model(data)
            L=L.coalesce().cpu(); ij=L.indices().numpy(); values=L.values().numpy()
            lower=csr_matrix((values,(ij[0],ij[1])),shape=A.shape).astype(np.float64)
            lower.sum_duplicates(); lower.sort_indices(); del L,data
            def precond(x,mat):
                return spsolve_triangular(mat.T.tocsr(),spsolve_triangular(mat,x,lower=True),lower=False)
            try:
                M=LinearOperator(A.shape,matvec=lambda v:precond(v,lower),dtype=np.float64)
                ni=[0]
                x,info=cg(A,b,rtol=1e-6,atol=0,maxiter=1000,M=M,callback=lambda _:ni.__setitem__(0,ni[0]+1))
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
                    x,info=cg(A,b,rtol=1e-6,atol=0,maxiter=1000,M=M,callback=lambda _:ci.__setitem__(0,ci[0]+1))
                    icits=ci[0] if info==0 else None
                except Exception as e: print('ic_solver_error',i,str(e),flush=True)
            rows.append({'index':i,'n':meta['n'],'nnz':meta['nnz'],'neural_iterations':neuralits,
                         'ic0_iterations':icits,'ic_breakdown_row':int(breakdown)})
            del A,b,lower,lower_ic,M
            if (i+1)%10==0: print('eval',split,i+1,'elapsed',time.perf_counter()-started,flush=True)
            if time.perf_counter()-started>3.75*3600:
                report.update(status='budget_gate_stopped',reason='evaluation incomplete within GPU allocation',evaluated={split:len(rows)},train_wall_seconds=report['train_wall_seconds'])
                save('l0b_selfcheck.json',report);return
        report[split+'_rows']=rows
    test=report['test_rows']; nits=[r['neural_iterations'] for r in test]; icits=[r['ic0_iterations'] for r in test]
    if None in nits or None in icits:
        report.update(status='evaluation_incomplete',reason='one or more solvers failed; cannot infer mean')
    else:
        nv=float(np.mean(nits)); iv=float(np.mean(icits))
        in_ic=(166.05*.8<=iv<=166.05*1.2)
        report.update(status='complete',neuralif_mean_iterations=nv,ic0_mean_iterations=iv,
                      neuralif_over_ic0_ratio=nv/iv,neuralif_in_134_202=134<=nv<=202,
                      selfcheck=('不判' if not in_ic else '过' if 134<=nv<=202 else '不过'),
                      reason=('reconstructed IC0 distribution differs from original' if not in_ic else None))
    save('l0b_selfcheck.json',report)

if __name__=='__main__':
    try: main()
    except BaseException as e:
        if not (OUT/'l0b_selfcheck.json').exists():
            save('l0b_selfcheck.json',{'status':'error','selfcheck':'不判','error':str(e),'traceback':traceback.format_exc()[-4000:]})
        raise
