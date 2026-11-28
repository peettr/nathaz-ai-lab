"""Frozen storm-held-out TopK SAE and correlation controls; run on Colab only."""
import json,os,sys,time,traceback
from pathlib import Path
T=time.time();R=Path('/content/l2612');P=R/'sae_progress.jsonl'
def log(**v):
 v['wall_s']=round(time.time()-T,2);s=json.dumps(v,default=str);print(s,flush=True)
 with P.open('a') as f:f.write(s+'\n')
try:
 import numpy as np,torch
 from torch import nn
 from scipy.stats import rankdata,spearmanr
 from sklearn.decomposition import PCA
 from sklearn.linear_model import Ridge
 from sklearn.model_selection import KFold
 torch.manual_seed(2612);np.random.seed(2612)
 records=json.loads((R/'cohort_2021.json').read_text());n=len(records)
 windows=[np.load(R/'windows'/f'{i:04d}.npz')['window'].astype(np.float32) for i in range(n)]
 tr=np.array([i for i,r in enumerate(records) if r['year']<=2020]);te=np.array([i for i,r in enumerate(records) if r['year']>=2021]);assert len(te)>=30
 X=np.concatenate([windows[i] for i in tr]);counts=np.array([len(windows[i]) for i in tr]);assert X.shape[1]==384
 mean=X.mean(axis=0);std=X.std(axis=0).clip(1e-5);X=(X-mean)/std
 # Internal validation uses only training storms, blocked by SID (one sample per storm).
 rng=np.random.default_rng(2612);val=rng.choice(len(tr),size=max(30,int(.2*len(tr))),replace=False)
 starts=np.r_[0,np.cumsum(counts)];vidx=np.concatenate([np.arange(starts[j],starts[j+1]) for j in val]);mask=np.ones(len(X),bool);mask[vidx]=False
 train=torch.from_numpy(X[mask]).to('cuda');valid=torch.from_numpy(X[vidx]).to('cuda')
 class SAE(nn.Module):
  def __init__(self):
   super().__init__();self.enc=nn.Linear(384,1536);self.dec=nn.Linear(1536,384,bias=False);nn.init.normal_(self.dec.weight,std=.02)
  def encode(self,x,k):
   z=torch.relu(self.enc(x));top=torch.topk(z,k,dim=-1);return torch.zeros_like(z).scatter_(1,top.indices,top.values)
  def forward(self,x,k):return self.dec(self.encode(x,k))
 def fit(k,epochs,seed,train,valid):
  torch.manual_seed(seed);model=SAE().to('cuda');optim=torch.optim.AdamW(model.parameters(),lr=.0005,weight_decay=1e-4)
  for ep in range(epochs):
   model.train();perm=torch.randperm(len(train),device='cuda');loss_sum=0.
   for part in perm.split(1024):
    pred=model(train[part],k);loss=(pred-train[part]).square().mean();optim.zero_grad();loss.backward();optim.step();loss_sum+=float(loss)*len(part)
   model.eval()
   with torch.no_grad():
    val_loss=sum(float((model(v,k)-v).square().sum()) for v in valid.split(2048))/(valid.numel() if valid.numel() else 1)
   log(stage='epoch',k=k,epoch=ep+1,train_mse=loss_sum/len(train),val_mse=val_loss)
  return model,val_loss
 choice=[]
 for k in (16,32,64):
  model,loss=fit(k,2,2612,train,valid);choice.append([k,loss]);del model;torch.cuda.empty_cache()
 k=min(choice,key=lambda x:x[1])[0];log(stage='selected',choice=choice,k=k)
 alltrain=torch.from_numpy(X).to('cuda');model,_=fit(k,5,2712,alltrain,valid)
 torch.save({'state':model.cpu().state_dict(),'mean':mean,'std':std,'k':k,'width':1536,'seed':2712},R/'sae.pt');model.to('cuda');model.eval()
 def encode(w):
  with torch.no_grad():
   z=model.encode(torch.from_numpy((w-mean)/std).to('cuda'),k).max(dim=0).values.cpu().numpy()
  return z
 Z=np.stack([encode(w) for w in windows]);np.save(R/'features.npy',Z.astype(np.float32))
 mean_sq=sum(float((model(a,k)-a).square().sum()) for a in alltrain.split(2048))/alltrain.numel()
 log(stage='features',shape=Z.shape,train_mse=mean_sq)
 props=['wind_kt','pres_hpa'];Y={p:np.array([r[p] if r[p] is not None else np.nan for r in records],float) for p in props}
 def corr(x,y):
  ok=np.isfinite(x)&np.isfinite(y)
  return float(spearmanr(x[ok],y[ok]).statistic) if ok.sum()>=10 and len(np.unique(x[ok]))>1 and len(np.unique(y[ok]))>1 else None
 def boot(x,y,idx,seed):
  local=np.array([i for i in idx if np.isfinite(y[i])]);prng=np.random.default_rng(seed)
  vals=[corr(x[prng.choice(local,len(local),replace=True)],y[prng.choice(local,len(local),replace=True)]) for _ in []] # deliberate no independent x/y resampling
  for _ in range(1000):
   draw=prng.choice(local,len(local),replace=True);v=corr(x[draw],y[draw]);
   if v is not None:vals.append(v)
  return np.quantile(vals,[.025,.975]).tolist() if vals else None
 candidates={}
 for p in props:
  ranks=sorted([(abs(corr(Z[:,j][tr],Y[p][tr]) or 0),j) for j in range(1536)],reverse=True)[:5]
  candidates[p]=[{'feature':int(j),'train_rho':corr(Z[:,j][tr],Y[p][tr]),'test_rho':corr(Z[:,j][te],Y[p][te]),'test_ci95':boot(Z[:,j],Y[p],te,2612+j)} for _,j in ranks]
 # Shuffle labels at the SID unit, once per permutation; one sample per SID in this bounded cohort.
 null={}
 for p in props:
  valid=te[np.isfinite(Y[p][te])];A=rankdata(Z[valid],axis=0);A=A-A.mean(axis=0);norm=np.sqrt((A*A).sum(axis=0));norm[norm==0]=np.inf
  y=rankdata(Y[p][valid]);y=y-y.mean();den=np.sqrt((y*y).sum())
  random=np.random.default_rng(2760+(p=='pres_hpa'))
  maxima=[]
  for _ in range(200):
   shuffled=random.permutation(y);maxima.append(float(np.max(abs(shuffled@A)/(den*norm))))
  null[p]={'max_200':max(maxima),'q95_200':float(np.quantile(maxima,.95)),'n_storms':len(valid)}
 # A comparable same-case PCA and ridge baseline fitted on training samples only.
 V=np.stack([w.max(axis=0) for w in windows]);pca=PCA(n_components=10,random_state=2612).fit(V[tr]);pc=pca.transform(V)
 baselines={}
 for p in props:
  train=tr[np.isfinite(Y[p][tr])];test=te[np.isfinite(Y[p][te])]
  cp=sorted([(abs(corr(pc[train,j],Y[p][train]) or 0),j) for j in range(10)],reverse=True)[0][1]
  kf=KFold(5,shuffle=True,random_state=2612);grid=[.01,.1,1,10,100,1000];err=[]
  for alpha in grid:
   scores=[]
   for a,b in kf.split(train):
    model_r=Ridge(alpha=alpha).fit(V[train[a]],Y[p][train[a]]);scores.append(np.mean((model_r.predict(V[train[b]])-Y[p][train[b]])**2))
   err.append(float(np.mean(scores)))
  alpha=grid[np.argmin(err)];pred=Ridge(alpha=alpha).fit(V[train],Y[p][train]).predict(V)
  baselines[p]={'pca_best_component':int(cp),'pca_train_rho':corr(pc[train,cp],Y[p][train]),'pca_test_rho':corr(pc[test,cp],Y[p][test]),'pca_ci95':boot(pc[:,cp],Y[p],test,3000+cp),'ridge_alpha':alpha,'ridge_test_rho':corr(pred[test],Y[p][test]),'n_test':len(test)}
 out={'n_train':len(tr),'n_test':len(te),'width':1536,'K':k,'K_selection_val_mse':choice,'train_reconstruction_normalized_mse':mean_sq,'candidates':candidates,'null':null,'baselines':baselines,'source':'NOAA IBTrACS v04r01 NA/WP, WeatherBench2 ERA5 1959-2022 derived zarr, ECMWF Pangu-Weather 24h ONNX'}
 (R/'correlations.json').write_text(json.dumps(out,indent=2,allow_nan=False));log(stage='done',candidates=candidates,null=null)
 (R/'sae.done').write_text('ok\n')
except BaseException as exc:
 log(stage='error',error=repr(exc),traceback=traceback.format_exc());(R/'sae.done').write_text('error\n');raise
