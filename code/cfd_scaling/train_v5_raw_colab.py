"""Native-grid UrbanTALES v5 alignment-only correction gate. Uses only internal validation for model selection.
No test scores are computed until a checkpoint has been frozen from validation.
"""
import os, json, time, random, re, zipfile, io, copy
from pathlib import Path
os.environ['OMP_NUM_THREADS']='2'; os.environ['OPENBLAS_NUM_THREADS']='2'
import numpy as np
from scipy.ndimage import rotate
import torch
from torch import nn
from torch.nn import functional as F

ROOT=Path('/content/cfd_scaling_v5_raw'); ROOT.mkdir(exist_ok=True)
S=json.loads(Path('/content/group_split_v5.json').read_text())
assert len(S['train_cases'])==371 and len(S['val_cases'])==34 and len(S['test_cases'])==100
assert not(set(S['train_groups'])&set(S['val_groups'])|set(S['val_groups'])&set(S['test_groups'])|set(S['train_groups'])&set(S['test_groups']))
assert all(re.search(r'_d\d+$',c) for c in S['type_by_case'])
Z=zipfile.ZipFile('/content/urbantales_native_v5.zip')
assert set(Z.namelist())=={c+'.npz' for c in S['type_by_case']}
# A statistical training-only scalar, NOT a casewise physical reference velocity.
# It cannot explain unknown case-to-case forcing; report raw-scale metrics.
raw={}; sm=ct=0.
for c in S['type_by_case']:
 with np.load(io.BytesIO(Z.read(c+'.npz'))) as d:
  h=d['height'].astype(np.float32); y=d['speed'].astype(np.float32); m=d['mask'].astype(bool)
 assert h.shape==y.shape==m.shape and m.any(),c
 raw[c]=(h,y,m)
 if c in S['train_cases']:
  sm+=float(y[m].sum());ct+=int(m.sum())
scale=sm/ct; assert .01<scale<100
print('DATA_READY',len(raw),'train_scalar',scale,flush=True)

def aligned(c):
 h,y,m=raw[c];a=int(c.rsplit('_d',1)[1])
 # PALM azimuth assumed counterclockwise from +x. For oblique cases, periodically
 # extend to 3x3 before rotating; central crop preserves original pixel pitch.
 def rot(arr,order):
  if a==0:return arr.copy()
  if a%90==0:return np.rot90(arr,-a//90).copy()
  hh,ww=arr.shape
  tiled=np.tile(arr,(3,3))
  r=rotate(tiled,-a,reshape=False,order=order,mode='nearest',prefilter=False)
  return r[hh:2*hh,ww:2*ww].copy()
 return rot(h,1)/40.,rot(y,1)/scale,rot(m.astype(np.float32),0)>.5
# Cache aligned arrays in CPU RAM for randomized cropping. Scoring is on aligned
# original-resolution fields (interpolated for oblique angles), not resized fields.
D={c:aligned(c) for c in S['type_by_case']}
print('ALIGNED_READY',len(D),'example_shapes',[(c,D[c][0].shape) for c in list(D)[:3]],flush=True)

class Block(nn.Module):
 def __init__(self,a,b):
  super().__init__();self.net=nn.Sequential(nn.Conv2d(a,b,3,padding=1),nn.BatchNorm2d(b),nn.ReLU(inplace=True),nn.Conv2d(b,b,3,padding=1),nn.BatchNorm2d(b),nn.ReLU(inplace=True))
 def forward(self,x):return self.net(x)
class UNet(nn.Module):
 def __init__(self):
  super().__init__();self.a=Block(1,16);self.b=Block(16,32);self.c=Block(32,64);self.d=Block(64,96);self.u=Block(160,64);self.v=Block(96,32);self.w=Block(48,16);self.out=nn.Conv2d(16,1,1)
 def forward(self,x):
  a=self.a(x);b=self.b(F.max_pool2d(a,2));c=self.c(F.max_pool2d(b,2));d=self.d(F.max_pool2d(c,2))
  q=self.u(torch.cat((F.interpolate(d,size=c.shape[-2:],mode='bilinear',align_corners=False),c),1))
  q=self.v(torch.cat((F.interpolate(q,size=b.shape[-2:],mode='bilinear',align_corners=False),b),1))
  q=self.w(torch.cat((F.interpolate(q,size=a.shape[-2:],mode='bilinear',align_corners=False),a),1))
  return F.relu(self.out(q))[:,0]

def sample(c,rng,side=192):
 h,y,m=D[c];hh,ww=h.shape
 i=int(rng.integers(0,hh));j=int(rng.integers(0,ww))
 ii=np.arange(i,i+side)%hh;jj=np.arange(j,j+side)%ww
 return h[np.ix_(ii,jj)],y[np.ix_(ii,jj)],m[np.ix_(ii,jj)]

def predict(net,c):
 h,_,_=D[c];hh,ww=h.shape
 x=torch.from_numpy(np.pad(h,((0,(-hh)%16),(0,(-ww)%16)),mode='wrap')[None,None]).cuda()
 with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):p=net(x)[0,:hh,:ww].float().cpu().numpy()
 return p

def evaluate(net,cases,keep_rows=False):
 net.eval();rows=[]
 for c in cases:
  _,yy,mm=D[c];p=predict(net,c);t=yy[mm];q=p[mm]
  mse=float(np.mean((q-t)**2));den=float(np.sum((t-t.mean())**2));r2=1-float(np.sum((q-t)**2))/den if den>1e-8 else None
  rows.append({'case':c,'type':S['type_by_case'][c],'mse':mse,'rmse_raw':float(np.sqrt(mse)*scale),'r2':r2,'pixels':int(mm.sum())})
 return {'mae':float(np.mean([r['mse']**.5 for r in rows])),'median_r2':float(np.median([r['r2'] for r in rows if r['r2'] is not None])),'ideal_median_r2':float(np.median([r['r2'] for r in rows if r['type']=='ideal' and r['r2'] is not None])) if any(r['type']=='ideal' for r in rows) else None,'rows':rows if keep_rows else None}

def run(seed):
 random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
 rng=np.random.default_rng(seed);net=UNet().cuda();opt=torch.optim.Adam(net.parameters(),lr=.001)
 train=S['train_cases']; best=float('inf');wait=0;hist=[];start=time.monotonic();best_epoch=0
 # 16 * 20 = 320 independently sampled physical-grid patches per epoch.
 # A validation pass every 5 epochs, patience 12 passes = >=60 additional epochs.
 for epoch in range(1,501):
  net.train(); losses=[]
  for batch in range(20):
   cs=rng.choice(train,size=16,replace=True)
   samples=[sample(c,rng) for c in cs]
   x=torch.from_numpy(np.stack([q[0] for q in samples])[:,None]).cuda();y=torch.from_numpy(np.stack([q[1] for q in samples])).cuda();m=torch.from_numpy(np.stack([q[2] for q in samples])).cuda()
   with torch.autocast('cuda',dtype=torch.bfloat16):p=net(x);loss=torch.abs(p[m]-y[m]).mean()
   opt.zero_grad(set_to_none=True);loss.backward();opt.step();losses.append(loss.item())
  if epoch%5:continue
  val=evaluate(net,S['val_cases']);v=val['mae'];hist.append({'epoch':epoch,'train_mae':float(np.mean(losses)),'val_case_rmse_scaled':v,'val_median_r2':val['median_r2']})
  print('EPOCH',seed,epoch,'train',round(float(np.mean(losses)),5),'val',round(v,5),'r2',round(val['median_r2'],3),'minutes',round((time.monotonic()-start)/60,1),flush=True)
  if v<best-.0005:
   best=v;wait=0;best_epoch=epoch
   torch.save({'state':net.state_dict(),'epoch':epoch,'scale':scale,'seed':seed,'val_mae':v},ROOT/f'best_{seed}.pt')
  else:wait+=1
  (ROOT/f'history_{seed}.json').write_text(json.dumps({'seed':seed,'history':hist,'best_epoch':best_epoch,'best_val':best,'elapsed_s':time.monotonic()-start},indent=2))
  if wait>=12 and epoch>=100:break
 print('FROZEN',seed,'best_epoch',best_epoch,'last_epoch',epoch,'minutes',round((time.monotonic()-start)/60,1),flush=True)
 assert best_epoch>0
 net.load_state_dict(torch.load(ROOT/f'best_{seed}.pt',weights_only=False)['state'])
 val=evaluate(net,S['val_cases'],True)
 # Test is opened once AFTER all model selection, for the frozen checkpoint only.
 test=evaluate(net,S['test_cases'],True)
 out={'seed':seed,'best_epoch':best_epoch,'last_epoch':epoch,'elapsed_s':time.monotonic()-start,'scale_training_only':scale,'validation':val,'test':test,'assumptions':['direction angle convention +x counterclockwise (requires source cross-check)','oblique rotation interpolation and periodic 3x3 extension','one pooled train-only speed scalar (not physical reference)','192-m random patches, 20 batches/epoch, 12 validation-check patience']}
 (ROOT/f'gate_{seed}.json').write_text(json.dumps(out,indent=2,allow_nan=False));print('GATE_RESULT',seed,'val_r2',val['median_r2'],'test_ideal_r2',test['ideal_median_r2'],flush=True)
 return out

for seed in (17,42,73):
 if (ROOT/f'gate_{seed}.json').exists():print('SKIP_EXISTING',seed,flush=True);continue
 run(seed)
print('GATE_COMPLETE',flush=True)
