"""L26.16-01 bounded XAI run, R21 LBM via L26.15 converted archive. Run only on Colab."""
import os,sys,time,json,csv,copy,math
import numpy as np, torch
from scipy.stats import rankdata
from pathlib import Path
from captum.attr import IntegratedGradients, GradientShap
sys.path.insert(0,'/content/code')
from common import TRAIN,VAL,TEST,LAGS,hist_feat,fit_norm,load,points
from models import tr_model
D=Path('/content/data'); O=Path('/content/results'); O.mkdir(exist_ok=True)
T=time.time(); torch.set_num_threads(4)
seed=261601; rng=np.random.default_rng(seed); torch.manual_seed(seed)
log=lambda *a:print(round(time.time()-T,2),*a,flush=True)
def dump(name,obj): (O/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False))
def corr(a,b):
 a=rankdata(np.asarray(a).flatten());b=rankdata(np.asarray(b).flatten());return float(np.corrcoef(a,b)[0,1])
def aggregate(a): # raw (B,75,51) -> absolute magnitude, mean frames, sum components
 return np.abs(a).reshape(-1,25,3,51).sum(2).mean(0)
def jac(a,b):
 x=set(np.argsort(a.flatten())[-5:]);y=set(np.argsort(b.flatten())[-5:]);return len(x&y)/len(x|y)
def passes(a,b):return bool(jac(a,b)>=.6 and corr(a,b)>=.7)
log('load data')
runs={k:load(k) for k in TRAIN+VAL+TEST}; n=fit_norm(runs)
Xtr=np.concatenate([hist_feat(runs[k],n,runs[k]['idx']) for k in TRAIN]).astype('f4');
xt=hist_feat(runs['A1_101'],n,runs['A1_101']['idx']).astype('f4');
Ytr=np.concatenate([runs[k]['cp'][runs[k]['idx']] for k in TRAIN]); ym=n.ym[8000:8003];ys=n.ys[8000:8003]
inds=np.sort(rng.choice(len(xt),200,replace=False)); x=xt[inds]; bg=Xtr[rng.choice(len(Xtr),100,replace=False)]; mu=Xtr.mean(0)
assert x.shape==(200,3825) and len(inds)==200
log('train',Xtr.shape,'test',xt.shape,'selected',inds[[0,-1]].tolist())
# Exactly reproduce L26.15 GPU PCA and ridge, in float64 eigensolver.
Xt=torch.as_tensor(Xtr,device='cuda',dtype=torch.float64); eig,V=torch.linalg.eigh(Xt.T@Xt)
W=V[:,-64:].flip(1).float(); scale=(Xt.float()@W).std(0); del Xt,V
# 1e5 alpha, previously selected on validation; no test-tuning.
X64=torch.as_tensor(Xtr,device='cuda'); Y=torch.as_tensor((Ytr[:,8000:8003]-ym)/ys,device='cuda')
R=torch.linalg.solve(X64.T@X64+1e5*torch.eye(3825,device='cuda'),X64.T@Y).detach();del X64,Y
coords,normals,ids=points(); E=torch.as_tensor(np.c_[coords[8000:8003],normals[8000:8003]],device='cuda'); assert ids[:3]==['V2','V3','V4']
m=tr_model(64,128);m.load_state_dict(torch.load('/content/code/tr_64_128_best.pt',weights_only=True,map_location='cuda'));m.eval()
W=W.detach();scale=scale.detach();mean=torch.as_tensor(mu,device='cuda')
class Head(torch.nn.Module):
 def __init__(self,model,tap,offset=0.):
  super().__init__();self.model=model;self.tap=tap;self.offset=offset
 def forward(self,z):
  f=(z-self.offset)@W/scale
  return self.model(f[:,None,:],embedding=E[self.tap][None,None,:].expand(len(z),-1,-1))[:,0,0]
heads=[Head(m,j).eval() for j in range(3)]
with torch.no_grad():
 xp=torch.as_tensor(xt[:16],device='cuda'); p=torch.stack([h(xp) for h in heads],1).cpu().numpy()*ys+ym
log('sanity output first',p[0].tolist())
# Replication check against frozen L26.15 outputs: large mismatch invalidates all XAI.
ref=np.load('/content/code/preds_taps.npz')['transolver'][:16,:3]
err=float(np.max(np.abs(p-ref)));log('replication max abs Cp',err)
if err>.015: raise RuntimeError('PCA/checkpoint prediction parity failed: '+str(err))
# Ridge analytic reference: reference is training mean (SHAP interventional linear background).
x_t=torch.as_tensor(x,device='cuda');mu_t=torch.as_tensor(mu,device='cuda');bg_t=torch.as_tensor(bg,device='cuda')
analytic=((x_t-mu_t)[...,None]*R[None]).detach().cpu().numpy()
class RidgeHead(torch.nn.Module):
 def __init__(self,j):
  super().__init__();self.linear=torch.nn.Linear(3825,1,bias=False,device='cuda')
  with torch.no_grad():self.linear.weight.copy_(R[:,j][None])
  self.linear.weight.requires_grad_(False)
 def forward(self,z):return self.linear(z)[:,0]
ridge_shap=[];ridge_ig=[]
for j in range(3):
 rh=RidgeHead(j).eval();baseline=mu_t[None].expand(len(x_t),-1)
 ridge_shap.append(GradientShap(rh).attribute(x_t,baselines=mu_t[None],n_samples=20,stdevs=0.).detach().cpu().numpy())
 ridge_ig.append(IntegratedGradients(rh).attribute(x_t,baselines=baseline,n_steps=64,internal_batch_size=20).detach().cpu().numpy())
ridge_shap=np.stack(ridge_shap,axis=-1);ridge_ig=np.stack(ridge_ig,axis=-1)
metrics={'seed':seed,'sample_indices':inds.tolist(),'source':'R21 LBM, L26.15 pathb','prediction_parity_max_Cp':err,'versions':{'torch':torch.__version__,'captum':__import__('captum').__version__,'physicsnemo':__import__('importlib').metadata.version('nvidia-physicsnemo')},'1a':{}}
for j,id in enumerate(ids[:3]):
 sc=corr(ridge_shap[:,:,j],analytic[:,:,j]);ic=corr(ridge_ig[:,:,j],analytic[:,:,j]);metrics['1a'][id]={'shap_spearman':sc,'ig_spearman':ic,'pass':bool(sc>=.95 and ic>=.95)}
np.savez_compressed(O/'attr_ridge.npz',shap=np.stack([aggregate(ridge_shap[:,:,j]) for j in range(3)]),ig=np.stack([aggregate(ridge_ig[:,:,j]) for j in range(3)]),probe_ids=np.array(json.load(open('/content/code/meta.json'))['pts']),lags_s=LAGS/5.,samples=inds)
log('1a complete')
if not all(v['pass'] for v in metrics['1a'].values()):
 dump('gate1a_error.json',metrics);raise RuntimeError('1a analytic reference mismatch; inspect before continuing')
# Benchmark formal configuration on 10 frames, full 64 IG steps, 100-background GradientSHAP.
ns=20 # each sample draws from the fixed pool of 100 training background frames

def attr(sh,ig,frames,background,step=64):
 chunks=[];its=[];comp=[]
 for xx in frames.split(10):
  a=sh.attribute(xx,baselines=background,n_samples=ns,stdevs=0.).detach().cpu().numpy();chunks.append(a)
  b=ig.attribute(xx,baselines=mean[None].expand(len(xx),-1),n_steps=step,internal_batch_size=20).detach().cpu().numpy();its.append(b)
  with torch.no_grad(): delta=(ig.forward_func(xx)-ig.forward_func(mean[None].expand(len(xx),-1))).cpu().numpy()
  comp.extend((np.abs(b.sum(1)-delta)/(np.abs(delta)+1e-6)).tolist())
 return np.concatenate(chunks),np.concatenate(its),comp
# Run full test configuration timing (10 frames x 3 heads; extrapolate all variants including deletion)
start=time.time()
for j in range(3):
 a,b,c=attr(GradientShap(heads[j]),IntegratedGradients(heads[j]),x_t[:10],bg_t)
bench=time.time()-start
# baseline 200/10, plus 1b 4 layers, 1d, and gate 2 => conservative 10 passes; deletion 3x101 batched forwards
rate=float(os.environ['OWN_CU_RATE']);setup=float(os.environ['SETUP_SECONDS']);remaining=float(os.environ['REMAINING_CU'])
estimate=(bench*20*10+300+setup)/3600*rate*1.2
metrics['budget']={'bench_seconds_10x3':bench,'passes_upper':10,'own_rate_CU_per_hour':rate,'setup_seconds':setup,'remaining_CU':remaining,'estimate_CU_20pct':estimate,'formula':'(bench_seconds_10x3 * 20 * 10 + 300 + setup_seconds)/3600 * own_rate_CU_per_hour * 1.2'}
dump('pilot.json',metrics);log('pilot',bench,'estimate CU',estimate)
if estimate>remaining:raise RuntimeError('budget projection above remaining CU, stop before full run')
if '--pilot' in sys.argv:
 log('PILOT_DONE');Path('/content/pilot.done').write_text('done');sys.exit(0)
# Full batch per tap; consistent importance = mean over 200 samples of sum of abs u/v/w.
A=[];I=[];comps=[]
for j in range(3):
 aa,ii,cc=attr(GradientShap(heads[j]),IntegratedGradients(heads[j]),x_t,bg_t);A.append(aa);I.append(ii);comps.append(cc);log('attribution tap',j,'done')
base=np.stack([aggregate(a) for a in A]);igm=np.stack([aggregate(a) for a in I]);
np.savez_compressed(O/'attr_transolver.npz',shap=base,ig=igm,probe_ids=np.array(json.load(open('/content/code/meta.json'))['pts']),lags_s=LAGS/5.,samples=inds,ig_completeness_relative=np.array(comps))
metrics['ig_completeness']={ids[j]:{'median':float(np.median(comps[j])),'p95':float(np.percentile(comps[j],95))}for j in range(3)}
# Randomize output then block-by-block cascade. Initial stage names are parameter name prefixes.
orig={k:v.detach().clone() for k,v in m.state_dict().items()}; names=list(m.named_modules()); layers=[(name,mod) for name,mod in names if isinstance(mod,torch.nn.Linear)]
# group by top-level module for cascade, display actual groups
names_by_group={}
for name,mod in layers:names_by_group.setdefault(name.split('.')[0],[]).append((name,mod))
log('linear groups',[(k,len(v)) for k,v in names_by_group.items()]);metrics['1b']={}
# Last-to-first groups, randomized increasingly; all learnable tensors incl norm in group reset where possible.
groups=list(dict.fromkeys(k.split('.')[0] for k,p in m.named_parameters() if p.requires_grad))
randomized=set();metrics['1b_randomized_parameters']={}
for group in groups[::-1]:
 with torch.no_grad():
  group_keys=[]
  for key,value in m.named_parameters():
   if key.split('.')[0]!=group:continue
   if 'norm' in key.lower() and key.endswith('weight'):
    value.normal_(1.,.1)
   elif 'norm' in key.lower() and key.endswith('bias'):
    value.normal_(0.,.1)
   elif value.ndim>1:torch.nn.init.kaiming_uniform_(value,a=math.sqrt(5))
   elif key.endswith('weight'):value.normal_(1.,.1)
   else:value.normal_(0.,.1)
   randomized.add(key);group_keys.append(key)
  metrics['1b_randomized_parameters'][group]=group_keys
 vals=[]
 for j in range(3):
  aa=np.concatenate([GradientShap(heads[j]).attribute(xx,baselines=bg_t,n_samples=ns,stdevs=0.).detach().cpu().numpy() for xx in x_t.split(10)])
  signed=aa.reshape(-1,25,3,51).sum(2).mean(0)
  signed0=A[j].reshape(-1,25,3,51).sum(2).mean(0)
  vals.append({'signed':corr(signed0,signed),'absolute':corr(base[j],aggregate(aa))})
 metrics['1b'][group]={ids[j]:vals[j] for j in range(3)};log('randomized',group,vals)
m.load_state_dict(orig)
assert randomized=={k for k,p in m.named_parameters() if p.requires_grad}
metrics['1b_pass']=bool(all(metrics['1b'][groups[0]][id]['signed']<=.5 and metrics['1b'][groups[0]][id]['absolute']<=.5 for id in ids[:3]))
# deletion top 10%=127 or 128: round ceiling. Same sampled 200 frames, random 100 masks.
metrics['1c']={};nr=math.ceil(25*51*.1)
for j,id in enumerate(ids[:3]):
 rank=np.argsort(base[j].reshape(-1))[-nr:];randoms=np.stack([rng.choice(1275,size=nr,replace=False) for _ in range(100)])
 def loss_for(masks):
  deltas=[]
  with torch.no_grad():
   y0=torch.cat([heads[j](z) for z in x_t.split(20)]).cpu().numpy()
   for mask in masks:
    z=x_t.clone().reshape(200,25,3,51);mz=mean.reshape(25,3,51);ii,ll=np.unravel_index(mask,(25,51));z[:,ii,:,ll]=mz[ii,:,ll];z=z.reshape(200,-1)
    yy=torch.cat([heads[j](zz) for zz in z.split(20)]).cpu().numpy();deltas.append(float(np.abs(yy-y0).mean()))
  return deltas
 d=loss_for([rank])[0];rd=loss_for(randoms);q=float(np.percentile(rd,95));metrics['1c'][id]={'top_mean_abs_delta_normalized_Cp':d,'random_p95':q,'pass':bool(d>=q)};log('deletion',id,d,q)
# translation compensated before PCA exactly; outputs and train mean background shift same, IG invariant.
metrics['1d']={}; shift=.5
for j,id in enumerate(ids[:3]):
 h=Head(m,j,shift).eval(); z=x_t+shift
 with torch.no_grad(): diff=float((heads[j](x_t)-h(z)).abs().max())
 assert diff<1e-5,diff
 a=GradientShap(h).attribute(z,baselines=bg_t+shift,n_samples=ns,stdevs=0.).detach().cpu().numpy();g=aggregate(a)
 b=IntegratedGradients(h).attribute(z,baselines=(mean+shift)[None].expand(200,-1),n_steps=64,internal_batch_size=20).detach().cpu().numpy()
 metrics['1d'][id]={'max_output_diff':diff,'shap_spearman':corr(base[j],g),'ig_spearman':corr(igm[j],aggregate(b)),'pass':bool(corr(base[j],g)>=.9 and corr(igm[j],aggregate(b))>=.9)};log('invariance',id,diff)
metrics['1_pass']=bool(all(all(metrics[k][id]['pass'] for id in ids[:3]) for k in ('1a','1c','1d')) and metrics['1b_pass'])
dump('phase1.json',metrics)
if not metrics['1_pass']:
 metrics['2']={'status':'未评估：关1未过'}
else:
 metrics['2']={}
 for j,id in enumerate(ids[:3]):
  # SHAP train mean background, and 1% standardized Gaussian perturbation, same RNG.
  avg=aggregate(GradientShap(heads[j]).attribute(x_t,baselines=mean[None],n_samples=ns,stdevs=0.).detach().cpu().numpy())
  noise=x_t+torch.as_tensor(rng.normal(0,.01,x.shape),device='cuda',dtype=torch.float32)
  noisy=aggregate(GradientShap(heads[j]).attribute(noise,baselines=bg_t,n_samples=ns,stdevs=0.).detach().cpu().numpy())
  metrics['2'][id]={label:{'jaccard':jac(base[j],other),'spearman':corr(base[j],other),'pass':passes(base[j],other)}for label,other in [('method',igm[j]),('background',avg),('noise_1pct',noisy)]}
  log('gate2',id,metrics['2'][id])
metrics['2_pass']=bool(metrics['1_pass'] and all(metrics['2'][id][k]['pass'] for id in ids[:3] for k in ('method','background','noise_1pct')))
meta=json.load(open('/content/code/meta.json'))
metrics['top3']={}
for j,id in enumerate(ids[:3]):
 top=np.argsort(base[j].sum(1))[-3:][::-1];metrics['top3'][id]=[{'probe':meta['pts'][k],'lag_s':float(LAGS[np.argmax(base[j,k])]/5.),'strength':float(base[j,k].sum())}for k in top]
metrics['elapsed_seconds']=time.time()-T;dump('gates_0_2_partial.json',metrics)
# matplotlib figure: source annotation is mandatory.
import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
fig,ax=plt.subplots(3,1,figsize=(12,11),constrained_layout=True)
for j,id in enumerate(ids[:3]):
 im=ax[j].imshow(base[j],aspect='auto',origin='lower',extent=[-.2,20.2,-.5,24.5]);ax[j].set_title(id+' Transolver GradientSHAP | attribution | (sum u,v,w; mean 200 frames)');ax[j].set_ylabel('Probe index');fig.colorbar(im,ax=ax[j]);ax[j].set_yticks(range(25),meta['pts'],fontsize=6)
ax[-1].set_xlabel('Lag (s)');fig.suptitle('Data source: R21 LBM / L26.15 converted path b; test A1_101',fontsize=11)
fig.savefig(O/'attr_heatmap.png',dpi=140);plt.close(fig)
log('DONE',metrics['1_pass'],metrics['2_pass'])
Path('/content/step1.done').write_text('done')
