"""UrbanTALES geometry-held-out 320x320 learning curve; run inside Colab A100.
Inputs: /content/urbantales_320.npz and /content/group_split_known_direction.json.
Outputs: /content/cfd_scaling_known_320_results/{metrics.json,learning_curve.png,example.png,run.log}.
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
R=Path('/content/cfd_scaling_known_320_results');R.mkdir(exist_ok=True)
D=np.load('/content/urbantales_320.npz'); S=json.loads(Path('/content/group_split_known_direction.json').read_text())
names=list(D['case']); ix={s:i for i,s in enumerate(names)}
assert set(S['type_by_case']).issubset(set(names)) and len(names)==538, 'extract IDs mismatch'
keep=np.array([i for i,s in enumerate(names) if s in S['type_by_case']]); names=[names[i] for i in keep]; ix={s:i for i,s in enumerate(names)}
H=D['height'][keep].astype(np.float32);Y=D['speed'][keep].astype(np.float32);M=D['mask'][keep].astype(bool)
assert H.shape==(528,320,320) and all(M[ix[s]].any() for s in names),'extraction must be complete'
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
  pred['B0'][j]=np.full((320,320),mean,np.float32)
  pred['B1'][j]=lut[BI[j]]
  zz=Z[j].reshape(-1,7);f=np.concatenate([zz,zz[:,:5]**2,zz[:,0:1]*zz[:,1:4]],axis=1)
  pred['B2'][j]=np.maximum(0,ridge.predict(scaler.transform(f)).reshape(320,320))
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

rec={'dataset':'UrbanTALES 320x320 diagnostic; original Uped scale; post-hoc known-direction cohort','resolution':[320,320],'test_groups':len(S['test_groups']),'test_cases':len(test),'runs':[]}
flush(rec)
for seed in (17,42,73):
 start=time.monotonic();ids=np.array([ix[c] for c in S['seeds'][str(seed)]['400']])
 b1=baseline(ids)['B1']; pred,hist=train_unet(ids,seed)
 entry={'seed':seed,'N':400,'seconds':time.monotonic()-start,'history':hist,'methods':{}}
 for method,pp in [('B1',b1),('UNet',pred)]:
  rows=score(pp,test);entry['methods'][method]={'summary':summarize(rows),'per_case':rows}
 u={};b={}
 for r in entry['methods']['UNet']['per_case']:u.setdefault(r['group'],[]).append(r['rmse'])
 for r in entry['methods']['B1']['per_case']:b.setdefault(r['group'],[]).append(r['rmse'])
 entry['win_vs_B1']=sum(np.mean(u[g])<np.mean(b[g]) for g in u)/len(u)
 # No unknown-direction examples are loaded or scored.
 rec['runs'].append(entry);flush(rec)
 print('RUN_320_COMPLETE',seed,{m:round(v['summary']['rmse'],5) for m,v in entry['methods'].items()},'elapsed',round(entry['seconds']),flush=True)
print('DIAGNOSTIC_320_COMPLETE',len(rec['runs']),flush=True)
