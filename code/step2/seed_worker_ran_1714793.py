"""L26.16-02 CRC GPU worker. pilot is an allocation on its own; full requires approved budget.
No training data is written outside RUN_ROOT. L26.15 data and step1 reference stay read-only.
"""
import argparse, importlib.metadata, json, os, sys, time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('mode', choices=['pilot', 'full'])
p.add_argument('--root', required=True)
p.add_argument('--source', required=True, help='L26.15 pathb converted root, read-only')
p.add_argument('--reference', required=True, help='step1 attr_transolver.npz, read-only')
p.add_argument('--seed0', required=True, help='L26.15 original tr_64_128_best.pt, read-only')
p.add_argument('--indices', required=True, help='step1 gates_0_2.json, read-only')
p.add_argument('--original-code', required=True, help='L26.15 pathb scripts, read-only')
a = p.parse_args()
root = Path(a.root).resolve(); root.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, a.original_code)
import numpy as np
import torch
from scipy.stats import spearmanr
from captum.attr import GradientShap
import common
common.D = a.source
common.OUT = str(root)
from common import TRAIN, VAL, TEST, fit_norm, hist_feat, load, points, rmse_corr
from models import tr_model, tr_pred

T = time.time()
def log(*xs): print(f'[{time.time()-T:.1f}s]', *xs, flush=True)
def save(name, obj):
    with open(root/name, 'w') as f: json.dump(obj, f, indent=2, ensure_ascii=False, allow_nan=False)
def sync(): torch.cuda.synchronize()
assert torch.cuda.is_available(), 'A10 CUDA allocation required'
torch.set_num_threads(4)
assert not (root / 'seed_gate2.json').exists(), 'Existing result: do not overwrite'
gpu_name=torch.cuda.get_device_name()
assert 'A10' in gpu_name.upper(), f'A10 budget only; allocation is {gpu_name}'
log('gpu', gpu_name, 'mode', a.mode)
runs = {k:load(k) for k in TRAIN+VAL+TEST}
n = fit_norm(runs)
Xtr = np.concatenate([hist_feat(runs[k],n,runs[k]['idx']) for k in TRAIN]).astype('f4')
Ytr = np.concatenate([runs[k]['cp'][runs[k]['idx']] for k in TRAIN]); Ytr = (Ytr-n.ym)/n.ys
Xva = hist_feat(runs['P303_pre'],n,runs['P303_pre']['idx']).astype('f4')
Yva = runs['P303_pre']['cp'][runs['P303_pre']['idx']]
test = runs['A1_101']; idx = test['idx']
Xte = hist_feat(test,n,idx).astype('f4'); Yte = test['cp'][idx][:,8000:8003]
ind_info = json.loads(Path(a.indices).read_text()); inds = np.asarray(ind_info['sample_indices'], dtype=int)
assert len(inds)==30 and len(np.unique(inds))==30 and np.all((inds>=0)&(inds<len(Xte)))
# PCA from training only, same GPU float64 eigensolver and column order as L26.15 run.py.
Xt = torch.as_tensor(Xtr, device='cuda', dtype=torch.float64)
w,V = torch.linalg.eigh(Xt.T@Xt); W=V[:,-64:].flip(1).float(); scale=(Xt.float()@W).std(0)
del Xt,w,V
Ftr=(torch.as_tensor(Xtr,device='cuda')@W/scale).cpu()
Fva=(torch.as_tensor(Xva,device='cuda')@W/scale).cpu()
Fte=(torch.as_tensor(Xte,device='cuda')@W/scale).cpu()
coords,normals,ids=points(); assert ids[:3]==['V2','V3','V4']
E=torch.as_tensor(np.c_[coords,normals],device='cuda'); assert E.shape==(8040,6)
Ytrt=torch.as_tensor(Ytr)
per=len(Ftr)//8; EPOCHS=40

def validate(m):
    sync(); t=time.time()
    pred=tr_pred(m,Fva,E,bs=2)*n.ys+n.ym
    sync()
    rmse=float(rmse_corr(pred,Yva)[0].mean())
    return rmse,time.time()-t

def train(seed, steps_limit=None):
    torch.manual_seed(seed); np.random.seed(seed)
    m=tr_model(64,128)
    opt=torch.optim.AdamW(m.parameters(),1e-3,weight_decay=1e-4)
    sch=torch.optim.lr_scheduler.OneCycleLR(opt,1e-3,total_steps=per*EPOCHS)
    best=(float('inf'),None,-1); hist=[]; times=[]; step=0
    for ep in range(EPOCHS):
        m.train(); perm=torch.randperm(len(Ftr)); L=0.
        for b in range(per):
            I=perm[b*8:(b+1)*8]; pts=torch.randperm(8040,device='cuda')[:2048]
            f=Ftr[I].to('cuda'); y=Ytrt[I].to('cuda')[:,pts]
            fx=f[:,None,:].expand(-1,2048,-1); e=E[pts][None].expand(8,-1,-1)
            sync(); t=time.time(); opt.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.bfloat16):
                loss=((m(fx,embedding=e)[...,0].float()-y)**2).mean()
            assert torch.isfinite(loss), 'NaN training loss'
            loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(),1.)
            opt.step(); sch.step(); sync(); times.append(time.time()-t)
            L+=loss.item(); step+=1
            if steps_limit and step>=steps_limit:
                return m, {'train_steps':step,'step_seconds_median_excl_first10':float(np.median(times[10:])),
                           'step_seconds_p95_excl_first10':float(np.percentile(times[10:],95)),
                           'per_epoch':per,'train_seconds':float(sum(times))}
        rmse,eval_sec=validate(m)
        hist.append({'epoch':ep,'loss':L/per,'validation_mean_rmse_Cp':rmse,'evaluation_seconds':eval_sec})
        log('seed',seed,'epoch',ep,'val',rmse,'eval_s',eval_sec)
        if rmse<best[0]:
            best=(rmse,{k:v.detach().cpu().clone() for k,v in m.state_dict().items()},ep)
            torch.save(best[1],root/f'seed{seed}_best.pt')
        save(f'seed{seed}_history.json',hist)
    m.load_state_dict(best[1]);m.eval()
    return m,{'seed':seed,'validation_mean_rmse_Cp':best[0],'best_epoch':best[2],
              'epoch_count':len(hist),'steps':step,'history':hist}

class Head(torch.nn.Module):
    def __init__(self, model, tap):
        super().__init__();self.model=model;self.tap=tap
    def forward(self,z):
        f=z@W/scale
        return self.model(f[:,None,:].expand(-1,8040,-1),
                          embedding=E[None].expand(len(z),-1,-1))[:,8000+self.tap,0]

# Same RNG sequence as step1 worker: first 30 test indices, then 100 training backgrounds.
rng=np.random.default_rng(261601)
assert np.array_equal(np.sort(rng.choice(len(Xte),30,replace=False)),inds), 'step1 sampling parity'
bg_indices=rng.choice(len(Xtr),100,replace=False)
background=torch.as_tensor(Xtr[bg_indices],device='cuda')
xs=torch.as_tensor(Xte[inds],device='cuda')

def attribute(model, frames):
    model.eval();out=[]
    for tap in range(3):
        h=Head(model,tap).eval(); seq=[]
        for row in frames.split(1):
            # Captum 0.8.0 GradientShap; same 100-background pool, 20 samples, stdevs=0.
            seq.append(GradientShap(h).attribute(row,baselines=background,n_samples=20,stdevs=0.).detach().cpu().numpy())
        out.append(np.concatenate(seq))
    return np.stack(out) # (3,frames,3825)

def summaries(raw):
    z=raw.reshape(3,-1,25,3,51)
    magnitude=np.abs(z).sum(3).mean(1)
    signed_u=z[:,:, :,0,:].mean(1)
    return magnitude,signed_u

if a.mode=='pilot':
    m, timing=train(1,steps_limit=60)
    # A full 8040-point validation pass is included, rather than treating training steps as total cost.
    vr,ev_sec=validate(m)
    sync();t=time.time(); attribute(m,xs[:3]);sync();attr_sec=time.time()-t
    pilot={'mode':'pilot','gpu':torch.cuda.get_device_name(),'timing':timing,
           'validation_seconds':ev_sec,'validation_mean_rmse_Cp_diagnostic_only':vr,
           'attribution_3frames_3taps_seconds':attr_sec,'elapsed_seconds':time.time()-T,
           'training_epochs':EPOCHS,'models_attribution':3,'frames_per_model':30,
           'formula':'spent_A10_h + 1.2*(2*40*(per_epoch*step_seconds_p95_excl_first10 + validation_seconds) + 3*(30/3)*attribution_3frames_3taps_seconds + setup_and_save_seconds)/3600 <= 3',
           'notes':'Add already-spent allocation time, setup/install and 20% buffer; pilot is diagnostic, not a trained seed-1 model.'}
    save('pilot.json',pilot);log('PILOT_DONE',pilot);sys.exit(0)

# The full allocation is authorized only after pilot budget/ComputeOps approval.
ref=np.load(a.reference);base=ref['shap'];assert base.shape==(3,25,51)
results={};signed=[]
for seed in (1,2):
    m,info=train(seed)
    sync();t=time.time(); pred=tr_pred(m,Fte,E,bs=2)[:,8000:8003]*n.ys[8000:8003]+n.ym[8000:8003];sync()
    e,c=rmse_corr(pred,Yte)
    info.update({'holdout_V2_V4':{ids[j]:{'rmse_Cp':float(e[j]),'corr':float(c[j])} for j in range(3)},
                 'holdout_eval_seconds':time.time()-t})
    sync();t=time.time();raw=attribute(m,xs);sync();mag,sgn=summaries(raw)
    info['attribution_seconds']=time.time()-t
    scores={}
    for j,id in enumerate(ids[:3]):
        x=set(np.argsort(base[j].ravel())[-5:]);y=set(np.argsort(mag[j].ravel())[-5:])
        jac=len(x&y)/len(x|y)
        rho=float(spearmanr(base[j].ravel(),mag[j].ravel()).statistic)
        scores[id]={'jaccard_top5':jac,'spearman_all_cells':rho,'pass':bool(jac>=.6 and rho>=.7)}
    info['gate2_by_tap']=scores; info['pass']=bool(all(x['pass'] for x in scores.values()))
    results[str(seed)]=info;signed.append(sgn)
    np.savez_compressed(root/f'seed{seed}_attr.npz',shap=mag,signed_u=sgn,frames=inds)
    save(f'partial_gate2_seed{seed}.json',{'status':'incomplete_until_seed0_signed_and_both_seeds','seeds':results})
    log('seed complete',seed,info['pass'])
# Seed 0 is recomputed with the same 30 frames/background, not inferred from unsigned magnitudes.
m0=tr_model(64,128)
m0.load_state_dict(torch.load(a.seed0,map_location='cuda',weights_only=True));m0.eval()
# The exact same reference magnitude algorithm; Captum's random baselines may give Monte Carlo variation.
raw0=attribute(m0,xs);mag0,signed0=summaries(raw0)
np.savez_compressed(root/'attr_signed_u.npz',signed_u=np.stack([signed0,*signed]),seeds=np.array([0,1,2]),
                    tap_ids=np.array(ids[:3]),frames=inds,background_train_indices=bg_indices,
                    lags_seconds=common.LAGS/5.,data_source='R21 LBM / L26.15 pathb')
final={'source':'R21 LBM / L26.15 pathb','method':'Captum GradientShap',
       'versions':{'torch':torch.__version__,'captum':__import__('captum').__version__,
                   'physicsnemo':importlib.metadata.version('nvidia-physicsnemo')},
       'sample_seed':261601,'sample_indices':inds.tolist(),'background_train_indices':bg_indices.tolist(),
       'reference_shap_shape':list(base.shape),'seed0_recomputed_shap':mag0.tolist(),
       'thresholds':{'jaccard_top5':0.6,'spearman_all_cells':0.7},'seeds':results,
       'pass':bool(all(results[str(s)]['pass'] for s in (1,2))),'elapsed_seconds':time.time()-T}
save('seed_gate2.json',final);log('FULL_DONE',final['pass'])
