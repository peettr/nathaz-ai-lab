"""Allocated CRC CPU: checkpoint finite probe + quality-mesh seed prescan."""
import json, os, sys, time, traceback
from pathlib import Path
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0/L0m')
sys.path[:0]=[str(ROOT),str(ROOT.parent/'repo'),str(ROOT/'vendor')]
import numpy as np
from l0m_generate import make_sample
from scipy.sparse import tril
from scipy.sparse.linalg import cg, LinearOperator, spsolve_triangular
import ctypes as C
out=ROOT/'cpu'/'out'
if '--dry-run' not in sys.argv:
    assert os.getenv('JOB_ID') or os.getenv('SGE_JOB_ID')
    out.mkdir(parents=True,exist_ok=True)
def emit(name,data):
    with (out/name).open('x') as f: json.dump(data,f,allow_nan=False,indent=2)

def checkpoint_probe():
    import torch, types
    from torch_geometric.data import Data
    numml=types.ModuleType('numml');sparse=types.ModuleType('numml.sparse');numml.sparse=sparse
    sys.modules['numml']=numml;sys.modules['numml.sparse']=sparse
    from l0i_compat import apply
    apply()
    from neuralif.models import NeuralIF
    def model_new():
        return NeuralIF(latent_size=8,message_passing_steps=3,skip_connections=True,
                        augment_nodes=True,global_features=0,decode_nodes=False,
                        normalize_diag=False,activation='relu',aggregate=None,
                        graph_norm=False,two_hop=False,edge_features=1,normalize=False)
    def graph(A,b):
        coo=A.tocoo(); edges=np.stack((coo.row,coo.col)).astype(np.int64)
        return Data(x=torch.as_tensor(np.asarray(b,dtype=np.float32).copy()).reshape(-1,1),
                    edge_index=torch.as_tensor(edges.copy()),
                    edge_attr=torch.as_tensor(coo.data.astype(np.float32,copy=True)).reshape(-1,1))
    ck=ROOT.parent/'L0k/gpu/out/own_model.pt'
    state=torch.load(ck,map_location='cpu',weights_only=True)
    counts={k:{'nan':int(torch.isnan(v).sum()),'inf':int(torch.isinf(v).sum()),'size':v.numel()} for k,v in state.items()}
    result={'checkpoint':str(ck),'parameters':counts,'param_nan':sum(x['nan'] for x in counts.values()),'param_inf':sum(x['inf'] for x in counts.values()),'forward':[]}
    model=model_new().eval();model.load_state_dict(state,strict=True)
    table=json.loads((ROOT.parent/'L0h/accepted_seeds.json').read_text())
    rows=[r for r in table['accepted'] if r['split']=='test'][:3]
    from l0i_generate import make_sample as old_sample
    for row in rows:
        A,b,_=old_sample(row['seed'],row['geometry'])
        with torch.no_grad(): L,_,_=model(graph(A,b))
        val=L.coalesce().values()
        result['forward'].append({'seed':row['seed'],'n':A.shape[0],'nonfinite':int((~torch.isfinite(val)).sum()),'nan':int(torch.isnan(val).sum()),'inf':int(torch.isinf(val).sum()),'nnz':val.numel()})
        print('CHECKPOINT',row['seed'],result['forward'][-1],flush=True)
    emit('checkpoint_finiteness.json',result)

def main():
    checkpoint_probe()
    lib=C.CDLL('/groups/kareem/[用户]/L26_24_LINSYS_20261115_B/libic0_B2.so')
    I=np.ctypeslib.ndpointer(dtype=np.int32,flags='C_CONTIGUOUS');D=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
    lib.ic0_factor.argtypes=[C.c_int,I,I,D,D];lib.ic0_factor.restype=C.c_int
    accepted=[]; stats={}; ic_sample=[]
    splits={'train':250,'val':5,'test':100}; bases={'train':1100000,'val':2100000,'test':3100000}
    start=time.monotonic()
    for split,target in splits.items():
        for geometry in range(3):
            attempted=rejected=0; seed=bases[split]+geometry*100000
            while len([r for r in accepted if r['split']==split and r['geometry']==geometry])<target:
                if attempted>=4000 or time.monotonic()-start>1.75*3600:
                    raise TimeoutError(f'{split}/{geometry} attempts={attempted}; no incomplete accepted table')
                attempted+=1
                try: A,b,m=make_sample(seed,geometry)
                except (ValueError,IndexError,FloatingPointError) as e:
                    rejected+=1
                    if rejected<=3: print('REJECT',split,geometry,seed,str(e),flush=True)
                    seed+=1;continue
                if split=='test' and len([r for r in ic_sample if r['geometry']==geometry])<10:
                    L=tril(A,format='csr');L.sort_indices();v=np.empty_like(L.data)
                    status=lib.ic0_factor(A.shape[0],L.indptr,L.indices,np.ascontiguousarray(L.data),v)
                    if status: ic_sample.append({'geometry':geometry,'seed':seed,'status':'breakdown','row':status})
                    else:
                        L.data=v;Lt=L.T.tocsr();cnt=[0]
                        op=LinearOperator(A.shape,dtype=np.float64,matvec=lambda w:spsolve_triangular(Lt,spsolve_triangular(L,w,lower=True),lower=False))
                        _,info=cg(A,b,M=op,rtol=1e-6,atol=0,maxiter=10000,callback=lambda _:cnt.__setitem__(0,cnt[0]+1))
                        ic_sample.append({'geometry':geometry,'seed':seed,'status':'converged' if info==0 else 'censored','iterations':cnt[0]})
                accepted.append(dict(split=split,**m))
                seed+=1
                if len(accepted)%100==0: print('ACCEPTED',len(accepted),'elapsed',time.monotonic()-start,flush=True)
            stats[f'{split}/{geometry}']={'attempted':attempted,'rejected':rejected,'rejection_rate':rejected/attempted,'accepted':target}
            print('CLASS',split,geometry,stats[f'{split}/{geometry}'],flush=True)
    assert len(accepted)==1065
    assert len({r['seed'] for r in accepted})==1065
    emit('accepted_seeds.json',{'status':'complete','accepted':accepted,'stats':stats,'source':'L0m own triangle quality mesh; not authors data'})
    by_class={str(g):{'count':len([r for r in ic_sample if r['geometry']==g]),'mean_converged':float(np.mean([r['iterations'] for r in ic_sample if r['geometry']==g and r['status']=='converged'])) if any(r['geometry']==g and r['status']=='converged' for r in ic_sample) else None} for g in range(3)}
    emit('ic_sample.json',{'rows':ic_sample,'by_geometry':by_class,'definition':'scipy cg rtol=1e-6 atol=0 x0=0'})
if __name__=='__main__':
    if '--dry-run' in sys.argv:
        import triangle as tr
        assert (ROOT.parent/'L0h/accepted_seeds.json').is_file()
        assert (ROOT.parent/'L0k/gpu/out/own_model.pt').is_file()
        assert (ROOT/'vendor').is_dir()
        assert Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_B/libic0_B2.so').is_file()
        print('DRY_RUN_IMPORT_AND_PATHS_OK',tr.__version__,flush=True)
    else:
        try: main()
        except BaseException:
            print(traceback.format_exc(),flush=True);raise
