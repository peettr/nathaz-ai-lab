"""UrbanTALES geometry-held-out 160x160 learning curve; run inside Colab A100.
Inputs: /content/urbantales_160.npz and /content/group_split_known_direction.json.
Outputs: /content/cfd_scaling_known_160_results/{metrics.json,learning_curve.png,example.png,run.log}.
"""
import os,json,time,math,copy,random,traceback,re
from pathlib import Path
os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2'
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from scipy.ndimage import distance_transform_edt,maximum_filter,uniform_filter,shift
from scipy.optimize import curve_fit
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path('/content/cfd_scaling_known_160_results');R.mkdir(exist_ok=True)
D=np.load('/content/urbantales_160.npz'); S=json.loads(Path('/content/group_split_known_direction.json').read_text())
names=list(D['case']); ix={s:i for i,s in enumerate(names)}
assert set(S['type_by_case']).issubset(set(names)) and len(names)==538, 'extract IDs mismatch'
keep=np.array([i for i,s in enumerate(names) if s in S['type_by_case']]); names=[names[i] for i in keep]; ix={s:i for i,s in enumerate(names)}
H=D['height'][keep].astype(np.float32);Y=D['speed'][keep].astype(np.float32);M=D['mask'][keep].astype(bool)
assert H.shape==(528,160,160) and all(M[ix[s]].any() for s in names),'extraction must be complete'
print('DATA',len(names),'test',len(S['test_cases']),'validation',len(S['val_cases']),'train',len(S['train_cases']),flush=True)
# Known-direction-only input; reject all missing angles, never insert 0-degree placeholders.
assert all(re.search(r'_d\d+$', s) for s in names)
angles=np.array([float(s.rsplit('_d',1)[1])*np.pi/180 for s in names],np.float32)
X=[];Z=[]
for i in range(len(names)):
 h=H[i]; a=angles[i]; solid=h>0.1
 dist=distance_transform_edt(~solid).astype(np.float32)/40
 # Approximate upstream occupancy and highest obstruction at 8,16,32 resized pixels.
 ups=[]
 for step in (8,16,32):
  hs=shift(h,(step*np.cos(a),step*np.sin(a)),order=0,mode='nearest',prefilter=False)
  ups.append(maximum_filter(hs,size=5)/100)
 density=uniform_filter(solid.astype(np.float32),size=17)
 x=np.stack([h/100,np.clip(dist,0,4),np.full_like(h,np.cos(a)),np.full_like(h,np.sin(a))],0)
 z=np.stack([np.clip(dist,0,4),np.clip(ups[0],0,2),np.clip(ups[1],0,2),np.clip(ups[2],0,2),density,np.full_like(h,np.cos(a)),np.full_like(h,np.sin(a))],-1)
 X.append(x);Z.append(z)
X=np.stack(X).astype(np.float32);Z=np.stack(Z).astype(np.float32)
val=np.array([ix[c] for c in S['val_cases']]);test=np.array([ix[c] for c in S['test_cases']]); typ=S['type_by_case']
assert not(set(S['test_groups'])&set(S['train_groups']))
# B1: (SDF distance, local/upstream max height, local building-density) lookup.
def bins(i):
 z=Z[i]
 a=np.digitize(z[...,0],[.025,.075,.15,.3,.6,1.2,2.5])
 b=np.digitize(np.maximum(z[...,1],z[...,2]),[.05,.15,.3,.6,1.0])
 c=np.digitize(z[...,4],[.02,.1,.3,.6]);return (a*6+b)*5+c
BI=np.stack([bins(i) for i in range(len(names))]); BCOUNT=8*6*5
class Block(nn.Module):
 def __init__(self,c,d):
  super().__init__(); self.net=nn.Sequential(nn.Conv2d(c,d,3,padding=1),nn.GroupNorm(4,d),nn.ReLU(),nn.Conv2d(d,d,3,padding=1),nn.GroupNorm(4,d),nn.ReLU())
 def forward(self,x):return self.net(x)
class UNet(nn.Module):
 def __init__(self):
  super().__init__();self.a=Block(4,16);self.b=Block(16,32);self.c=Block(32,64);self.d=Block(64,96);self.u=Block(96+64,64);self.v=Block(64+32,32);self.w=Block(32+16,16);self.out=nn.Conv2d(16,1,1)
 def forward(self,x):
  a=self.a(x);b=self.b(F.avg_pool2d(a,2));c=self.c(F.avg_pool2d(b,2));d=self.d(F.avg_pool2d(c,2));q=self.u(torch.cat([F.interpolate(d,size=c.shape[-2:],mode='bilinear',align_corners=False),c],1));q=self.v(torch.cat([F.interpolate(q,size=b.shape[-2:],mode='bilinear',align_corners=False),b],1));q=self.w(torch.cat([F.interpolate(q,size=a.shape[-2:],mode='bilinear',align_corners=False),a],1));return F.softplus(self.out(q)[:,0])
def group(c):return c.rsplit('_d',1)[0]
def score(pred,indices):
 rows=[]
 for j in indices:
  m=M[j];t=Y[j][m];p=pred[j][m]
  ss=((t-t.mean())**2).sum(); r2=1-float(((t-p)**2).sum()/ss) if ss>1e-8 else None
  rows.append({'case':names[j],'group':group(names[j]),'type':typ[names[j]],'rmse':float(np.sqrt(np.mean((t-p)**2))),'r2':r2,'n_pixels':int(m.sum())})
 return rows
def summarize(rows):
 # Pairwise comparability: each method evaluated on identical fixed test cases.
 geom={}
 for row in rows:geom.setdefault(row['group'],[]).append(row)
 group_rmses=np.array([np.mean([x['rmse'] for x in v]) for v in geom.values()]);valid=[x['r2'] for x in rows if x['r2'] is not None]
 rng=np.random.default_rng(4512); draws=rng.integers(0,len(geom),size=(1000,len(geom)))
 boot=group_rmses[draws].mean(axis=1)
 vals=list(geom.values()); boot_r2=np.array([np.median([r['r2'] for i in draw for r in vals[i] if r['r2'] is not None]) for draw in draws])
 return {'median_r2':float(np.median(valid)),'median_r2_ci95':list(map(float,np.quantile(boot_r2,[.025,.975]))),'rmse':float(group_rmses.mean()),'rmse_ci95':list(map(float,np.quantile(boot,[.025,.975]))),'real_median_r2':float(np.median([x['r2'] for x in rows if x['type']=='real' and x['r2'] is not None])),'ideal_median_r2':float(np.median([x['r2'] for x in rows if x['type']=='ideal' and x['r2'] is not None])),'real_rmse':float(np.mean([x['rmse'] for x in rows if x['type']=='real'])),'ideal_rmse':float(np.mean([x['rmse'] for x in rows if x['type']=='ideal']))}
def baseline(train_ids):
 rng=np.random.default_rng(910)
 # B0 pooled fluid mean; B1 bin means; B2 polynomial ridge with explicit upstream features.
 targets=np.concatenate([Y[i][M[i]].reshape(-1) for i in train_ids]);mean=float(targets.mean())
 su=np.zeros(BCOUNT,np.float64);ct=np.zeros(BCOUNT,np.float64)
 for i in train_ids:
  b=BI[i][M[i]].ravel();t=Y[i][M[i]].ravel();su+=np.bincount(b,weights=t,minlength=BCOUNT);ct+=np.bincount(b,minlength=BCOUNT)
 lut=np.divide(su,ct,out=np.full_like(su,mean),where=ct>0)
 # Balanced pixel sampling by case, fit strictly on train IDs.
 feats=[]; ys=[]
 for i in train_ids:
  valid=np.flatnonzero(M[i].ravel());chosen=rng.choice(valid,size=min(320,len(valid)),replace=False)
  zz=Z[i].reshape(-1,7)[chosen];feats.append(np.concatenate([zz,zz[:,:5]**2,zz[:,0:1]*zz[:,1:4]],axis=1));ys.append(Y[i].ravel()[chosen])
 scaler=StandardScaler().fit(np.concatenate(feats));ridge=Ridge(alpha=200).fit(scaler.transform(np.concatenate(feats)),np.concatenate(ys))
 pred={k:{} for k in ['B0','B1','B2']}
 for j in test:
  pred['B0'][j]=np.full((160,160),mean,np.float32)
  pred['B1'][j]=lut[BI[j]]
  zz=Z[j].reshape(-1,7);f=np.concatenate([zz,zz[:,:5]**2,zz[:,0:1]*zz[:,1:4]],axis=1)
  pred['B2'][j]=np.maximum(0,ridge.predict(scaler.transform(f)).reshape(160,160))
 return pred

def train_unet(train_ids,seed,kind='UNet'):
 random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
 device='cuda' if torch.cuda.is_available() else 'cpu'; assert device=='cuda'
 if kind=='OldAKO':
  from old_best_model_source import anisotropic_kernel_operator_unet
  net=anisotropic_kernel_operator_unet(in_channels=4,n_c=20,depth=6).to(device)
 else:net=UNet().to(device)
 def forward(x):
  y=net(x)
  if y.ndim==4:y=y[:,0]
  return F.softplus(y) if kind=='OldAKO' else y
 opt=torch.optim.AdamW(net.parameters(),lr=.0004 if kind=='OldAKO' else .001,weight_decay=1e-5)
 xv=torch.tensor(X[val],device=device);yv=torch.tensor(Y[val],device=device);mv=torch.tensor(M[val],device=device)
 best=1e10;best_state=None;patience=0;hist=[]
 for epoch in range(1,61):
  net.train();order=np.random.permutation(train_ids); losses=[]
  for chunk in np.array_split(order,math.ceil(len(order)/16)):
   xx=torch.tensor(X[chunk],device=device);yy=torch.tensor(Y[chunk],device=device);mm=torch.tensor(M[chunk],device=device)
   with torch.autocast(device_type='cuda',dtype=torch.bfloat16):
    pp=forward(xx);loss=((pp[mm]-yy[mm])**2).mean()
   opt.zero_grad(set_to_none=True);loss.backward();opt.step();losses.append(float(loss.detach()))
  if epoch%2==0:
   net.eval();vq=[]
   with torch.no_grad(),torch.autocast(device_type='cuda',dtype=torch.bfloat16):
    for k in range(0,len(val),8):
     pp=forward(xv[k:k+8]);vq.append(float(((pp[mv[k:k+8]]-yv[k:k+8][mv[k:k+8]])**2).mean()))
   v=float(np.mean(vq));hist.append([epoch,float(np.mean(losses)),v])
   if v<best-1e-5:best=v;best_state=copy.deepcopy({k:t.cpu() for k,t in net.state_dict().items()});patience=0
   else:patience+=1
   if epoch%10==0:print('EPOCH',len(train_ids),seed,epoch,'train',round(np.mean(losses),5),'val',round(v,5),flush=True)
   if patience>=7:break
 net.load_state_dict(best_state);net.eval();pred={}
 with torch.no_grad(),torch.autocast(device_type='cuda',dtype=torch.bfloat16):
  for k in range(0,len(test),8):
   ids=test[k:k+8];p=forward(torch.tensor(X[ids],device=device)).float().cpu().numpy()
   for i,j in enumerate(ids):pred[j]=p[i]
 return pred,hist

def flush(out):
 (R/'metrics.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False))
rec=json.loads((R/'metrics.json').read_text()) if (R/'metrics.json').exists() else {'dataset':'UrbanTALES old CRC read-only, 160x160 resized Uped; simulated PALM field, not observations','resolution':[160,160],'train_validation_cases':len(val),'test_cases':len(test),'test_groups':len(S['test_groups']),'runs':[]}
assert rec['test_cases']==len(test) and rec['train_validation_cases']==len(val)
flush(rec)
for seed in (17,42,73):
 for n in (50,100,200,400):
  if any(r['seed']==seed and r['N']==n for r in rec['runs']):
   print('SKIP_COMPLETED',seed,n,flush=True);continue
  start=time.monotonic();ids=np.array([ix[c] for c in S['seeds'][str(seed)][str(n)]])
  oldhist=[]
  base=baseline(ids);pr,hist=train_unet(ids,seed);base['UNet']=pr
  if False and n==400: # old architecture lower priority under 20 CU
   print('OLD_ARCH_START',seed,flush=True)
   try:
    oldpred,oldhist=train_unet(ids,seed,kind='OldAKO');base['OldAKO']=oldpred
   except Exception as e:
    oldhist=[];print('OLD_ARCH_FAILED',seed,repr(e),flush=True)
  run={'seed':seed,'N':n,'methods':{},'history':hist,'old_history':oldhist if n==400 else [],'seconds':time.monotonic()-start}
  for method,pp in base.items():
   rows=score(pp,test);run['methods'][method]={'summary':summarize(rows),'per_case':rows}
  for method in ['B0','B1','B2']:
   unet_groups={};baseline_groups={}
   for row in run['methods']['UNet']['per_case']:unet_groups.setdefault(row['group'],[]).append(row['rmse'])
   for row in run['methods'][method]['per_case']:baseline_groups.setdefault(row['group'],[]).append(row['rmse'])
   run['methods']['UNet'][f'win_vs_{method}']=sum(np.mean(unet_groups[g])<np.mean(baseline_groups[g]) for g in unet_groups)/len(unet_groups)
  # This revised main analysis evaluates only known-direction records.
  rec['runs'].append(run);flush(rec)
  print('RUN_COMPLETE',seed,n,{k:round(v['summary']['rmse'],4) for k,v in run['methods'].items()},'seconds',round(run['seconds']),flush=True)
  if n==400 and seed==17:
   j=next(j for j in test if typ[names[j]]=='ideal');fig,ax=plt.subplots(1,3,figsize=(12,4));choice=min(('B0','B1','B2'),key=lambda k:run['methods'][k]['summary']['rmse'])
   for a,p,label in zip(ax,[Y[j],pr[j],base[choice][j]],['UrbanTALES truth','U-Net',choice]):
    im=a.imshow(np.where(M[j],p,np.nan),vmin=0,vmax=2,cmap='viridis');a.set_title(label);a.axis('off')
   fig.suptitle('UrbanTALES simulated field, '+names[j]+'; 160x160');fig.colorbar(im,ax=ax.ravel().tolist());fig.savefig(R/'example.png',dpi=150);plt.close(fig)
# Across seed mean+sd, each case-level 95% CI already in metrics.
summary=[]
for n in (50,100,200,400):
 for method in ('B0','B1','B2','UNet'):
  a=[r['methods'][method]['summary'] for r in rec['runs'] if r['N']==n];summary.append({'N':n,'method':method,'mean_rmse':float(np.mean([v['rmse'] for v in a])),'sd_rmse':float(np.std([v['rmse'] for v in a],ddof=1)),'mean_median_r2':float(np.mean([v['median_r2'] for v in a])),'mean_real_median_r2':float(np.mean([v['real_median_r2'] for v in a])),'mean_ideal_median_r2':float(np.mean([v['ideal_median_r2'] for v in a]))})
rec['summary']=summary
fig,ax=plt.subplots(figsize=(7,5))
for method in ('B0','B1','B2','UNet'):
 ss=[v for v in summary if v['method']==method];ax.errorbar([v['N'] for v in ss],[v['mean_rmse'] for v in ss],yerr=[v['sd_rmse'] for v in ss],marker='o',label=method)
ax.set_xscale('log');ax.set_xticks([50,100,200,400]);ax.set_xticklabels([50,100,200,400]);ax.set_ylabel('Geometry-mean RMSE (original Uped scale; post-hoc known-direction cohort)');ax.set_xlabel('Training cases N');ax.legend();ax.grid();fig.text(.02,.01,'UrbanTALES simulated PALM pedestrian wind; old CRC read-only; 160x160 resize',fontsize=8);fig.tight_layout(rect=(0,.04,1,1));fig.savefig(R/'learning_curve.png',dpi=150);plt.close(fig)
# Fit a*N^-b+c with constrained asymptote; 4 points only: extrapolation diagnostic, not measured evidence.
ns=np.array([50,100,200,400]); err=np.array([next(v['mean_rmse'] for v in summary if v['N']==n and v['method']=='UNet') for n in ns]);sd=np.array([next(v['sd_rmse'] for v in summary if v['N']==n and v['method']=='UNet') for n in ns])
try:
 def f(n,a,b,c):return a*n**(-b)+c
 popt,_=curve_fit(f,ns,err,p0=[2,.5,max(0,err[-1]*.6)],bounds=([0,.01,0],[100,3,max(err)]),maxfev=50000)
 rec['curve_fit']={'a_b_c':list(map(float,popt)),'rmse_1600':float(f(1600,*popt))}
except Exception as e:rec['curve_fit']={'error':str(e)}
flush(rec);print('BENCHMARK_COMPLETE',len(rec['runs']),'runs',flush=True)
