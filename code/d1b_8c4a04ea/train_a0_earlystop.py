"""A0-only 6-hour autoregressive WeatherBench v1 5.625-degree ViT.
All evaluation targets follow the frozen 2017-18 period; model selection uses 2016 only.
Run ONLY in isolated Colab GPU runtime after stage_weatherbench.py succeeds.
"""
import argparse
import calendar
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import random
import time

import netCDF4
import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader

FIELDS = ['z','t','t2m','u10','v10']
YEARS = range(1979,2019)
LEADS = [1,4,8,12]

class ViT(nn.Module):
    def __init__(self, conditional=False):
        super().__init__()
        self.patch = nn.Conv2d(13,320,kernel_size=(2,4),stride=(2,4))
        self.pos = nn.Parameter(torch.zeros(1,256,320))
        self.blocks = nn.ModuleList([nn.TransformerEncoderLayer(320,8,1280,0.0,
            activation='gelu',batch_first=True,norm_first=True) for _ in range(7)])
        self.conditional = conditional
        if conditional:
            self.cross = nn.ModuleList([nn.MultiheadAttention(320,8,batch_first=True)
                                        for _ in self.blocks])
            self.cond_proj = nn.Linear(384,320)
        self.norm = nn.LayerNorm(320)
        self.output = nn.Linear(320,2*4*5)
    def forward(self, previous, current, static, condition=None):
        b = current.shape[0]
        x = torch.cat([previous,current,static.expand(b,-1,-1,-1)],dim=1)
        x = self.patch(x).flatten(2).transpose(1,2)+self.pos
        for i,block in enumerate(self.blocks):
            x = block(x)
            if self.conditional:
                assert condition is not None
                ctx=self.cond_proj(condition).unsqueeze(1)
                x=x+self.cross(x,ctx,ctx,need_weights=False)[0]
        x = self.output(self.norm(x)).reshape(b,16,16,5,2,4)
        return x.permute(0,3,1,4,2,5).reshape(b,5,32,64)

class Series:
    def __init__(self, root):
        self.root=pathlib.Path(root)
        assert (self.root/'stage.done').exists(), 'dataset not staged fully'
        self.year={}
        for year in YEARS:
            arrays=[np.load(self.root/f'{f}_{year}_6h.npy',mmap_mode='r') for f in FIELDS]
            assert len(set(a.shape for a in arrays))==1
            self.year[year]=arrays
        with netCDF4.Dataset(str(self.root/'constants_5.625deg.nc')) as nc:
            print('STATIC_VARS',[(k,v.dimensions,v.shape) for k,v in nc.variables.items()],flush=True)
            def one_of(names):
                for name in names:
                    if name in nc.variables:
                        v=np.asarray(nc.variables[name][:]).squeeze().astype(np.float32)
                        if v.shape==(32,64): return v
                raise KeyError(names)
            land=one_of(['lsm','land_sea_mask','land_mask'])
            topo=one_of(['orography','z','geopotential','oro'])
            latvar=nc.variables['lat'] if 'lat' in nc.variables else nc.variables['latitude']
            lat=np.asarray(latvar[:],dtype=np.float32)
            assert lat.shape==(32,)
            self.lat=lat
            self.static=np.stack([(topo-topo.mean())/(topo.std()+1e-6),land,
                       np.broadcast_to(np.sin(np.deg2rad(lat))[:,None],(32,64))]).astype('f4')
        assert np.isfinite(self.static).all()
    def frame(self,year,index):
        return np.stack([a[index] for a in self.year[year]])
    def n(self,year):return len(self.year[year][0])

class Samples(Dataset):
    def __init__(self,series,years,mean,std):
        self.series=series;self.mean=mean;self.std=std
        self.keys=[(y,i) for y in years for i in range(1,series.n(y)-1)]
    def __len__(self):return len(self.keys)
    def __getitem__(self,index):
        y,i=self.keys[index]; s=self.series
        return tuple(torch.from_numpy(((s.frame(y,j)-self.mean)/self.std).astype('f4'))
                     for j in (i-1,i,i+1))

def training_stats(series):
    # annual sums: training period only, no validation/test leakage
    sums=np.zeros((5,),dtype='f8'); squares=sums.copy(); count=0
    for year in range(1979,2016):
        for j,a in enumerate(series.year[year]):
            for lo in range(0,len(a),512):
                x=np.asarray(a[lo:lo+512],dtype='f8'); sums[j]+=x.sum(); squares[j]+=(x*x).sum()
        count+=series.n(year)*32*64
    mean=sums/count;std=np.sqrt(squares/count-mean*mean)
    assert np.isfinite(std).all() and (std>0).all()
    return mean.astype('f4')[:,None,None],std.astype('f4')[:,None,None]

def climate(series):
    # 1979-2015 mean for same calendar month/day/UTC hour, with leap-day fallback.
    table={};counts={}
    for year in range(1979,2016):
        start=dt.datetime(year,1,1)
        for i in range(series.n(year)):
            d=start+dt.timedelta(hours=i*6); key=(d.month,d.day,d.hour)
            if key not in table:
                table[key]=np.zeros((5,32,64),dtype='f8');counts[key]=0
            table[key]+=series.frame(year,i);counts[key]+=1
    return {key:(table[key]/counts[key]).astype('f4') for key in table}

def climate_at(table,d):
    return table[(d.month,d.day,d.hour)]

def score_add(acc,pred,truth,weights):
    # lat weights normalized over grid; aggregate SSE before sqrt, not mean of per-case RMSE.
    for v in range(5):
        acc[v]+=float(np.sum(((pred[v]-truth[v])**2)*weights))
    ps=np.hypot(pred[3],pred[4]);ts=np.hypot(truth[3],truth[4])
    acc[5]+=float(np.sum(((ps-ts)**2)*weights))

def evaluate(series,model,mean,std,static,device,table,seed,out):
    model.eval();weights=np.cos(np.deg2rad(series.lat)).astype('f8')[:,None]
    weights=np.broadcast_to(weights/(weights.sum()*64), (32,64))
    scores={m:{lead:np.zeros(6,dtype='f8') for lead in LEADS}
            for m in ('vit','persistence','climatology')}
    counts={lead:0 for lead in LEADS}
    batch_size=32
    with torch.inference_mode():
        for year in (2017,2018):
            n=series.n(year);start=dt.datetime(year,1,1)
            for begin in range(1,n-12,batch_size):
                idx=list(range(begin,min(begin+batch_size,n-12)))
                prev=np.stack([series.frame(year,i-1) for i in idx])
                initial=np.stack([series.frame(year,i) for i in idx])
                p=torch.from_numpy((prev-mean)/std).to(device)
                x=torch.from_numpy((initial-mean)/std).to(device)
                for step in range(1,13):
                    z=model(p,x,static);p,x=x,z
                    if step not in LEADS:continue
                    estimate=(z.cpu().numpy()*std+mean)
                    for j,i in enumerate(idx):
                        truth=series.frame(year,i+step)
                        valid=start+dt.timedelta(hours=(i+step)*6)
                        score_add(scores['vit'][step],estimate[j],truth,weights)
                        score_add(scores['persistence'][step],initial[j],truth,weights)
                        score_add(scores['climatology'][step],climate_at(table,valid),truth,weights)
                        counts[step]+=1
                if begin%(batch_size*32)==1:
                    print('eval',seed,year,begin,n,flush=True)
    result={'seed':seed,'test_years':[2017,2018],'counts':counts,'rmse':{
        method:{str(lead):dict(zip(FIELDS+['speed10'],[math.sqrt(x/counts[lead])
              for x in scores[method][lead]])) for lead in LEADS} for method in scores}}
    p=out/f'a0_seed{seed}_metrics.json'; assert not p.exists()
    p.write_text(json.dumps(result,indent=2));print('SCORED',p,flush=True)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',default='/content/l2631/weatherbench')
    parser.add_argument('--out',default='/content/l2631/output')
    parser.add_argument('--seeds',type=int,nargs='+',default=[11,23,37])
    parser.add_argument('--epochs',type=int,default=60)
    parser.add_argument('--batch',type=int,default=64)
    a=parser.parse_args(); out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(4)
    series=Series(a.root)
    mean,std=training_stats(series)
    config={'fields':FIELDS,'train_years':[1979,2015],'validation_year':2016,
            'test_years':[2017,2018],'input_steps':2,'horizon_hours':[6,24,48,72],
            'patch':[2,4],'width':320,'blocks':7,'heads':8,'batch':a.batch,
            'epochs_max':a.epochs,'early_stop_relative_improvement':0.005,
            'early_stop_patience':3,'optimizer':'AdamW','lr':0.0003,'seeds':a.seeds,
            'gpu':torch.cuda.get_device_name(0),'torch':torch.__version__,
            'precision':'float32 (T4 compatibility)',
            'mean':mean[:,0,0].tolist(),'std':std[:,0,0].tolist()}
    cfgpath=out/'config.json';assert not cfgpath.exists();cfgpath.write_text(json.dumps(config,indent=2))
    train=Samples(series,range(1979,2016),mean,std)
    valid=Samples(series,[2016],mean,std)
    static=torch.from_numpy(series.static[None]).to('cuda')
    lat=torch.from_numpy(np.cos(np.deg2rad(series.lat)).astype('f4')[None,None,:,None]).to('cuda')
    print('PARAMS',sum(p.numel() for p in ViT().parameters()),'TRAIN',len(train),'VAL',len(valid),flush=True)
    table=climate(series)
    for seed in a.seeds:
        if (out/f'a0_seed{seed}_metrics.json').exists():
            print('SKIP completed seed',seed,flush=True);continue
        random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
        model=ViT().to('cuda');opt=torch.optim.AdamW(model.parameters(),lr=0.0003,weight_decay=0.01)
        loader=DataLoader(train,batch_size=a.batch,shuffle=True,num_workers=2,pin_memory=True)
        vloader=DataLoader(valid,batch_size=a.batch,num_workers=2,pin_memory=True)
        best=float('inf');best_epoch=0; stale=0; history=[]
        for epoch in range(1,a.epochs+1):
            t0=time.monotonic();model.train();losses=[]
            for previous,current,target in loader:
                previous=previous.to('cuda',non_blocking=True);current=current.to('cuda',non_blocking=True)
                target=target.to('cuda',non_blocking=True)
                pred=model(previous,current,static)
                loss=((((pred.float()-target)**2)*lat).mean())
                opt.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(model.parameters(),1.0);opt.step()
                losses.append(loss.item())
            model.eval();vsum=0.0;vn=0
            with torch.inference_mode():
                for previous,current,target in vloader:
                    pred=model(previous.to('cuda'),current.to('cuda'),static).float()
                    err=((pred-target.to('cuda'))**2*lat).mean(dim=(1,2,3))
                    vsum+=float(err.sum());vn+=len(err)
            val=vsum/vn
            print('EPOCH',seed,epoch,'train',float(np.mean(losses)),'val',val,
                  'seconds',round(time.monotonic()-t0,1),flush=True)
            # Select the checkpoint by best validation loss, but stop when
            # three successive epochs improve <0.5% over the previous epoch.
            if val<best:
                best=val;best_epoch=epoch
                state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
            previous_val=history[-1] if history else float('inf')
            improvement=(previous_val-val)/previous_val if history else float('inf')
            history.append(val)
            stale=stale+1 if improvement<0.005 else 0
            progress={'seed':seed,'epoch':epoch,'best_epoch':best_epoch,
                      'best_val':best,'current_val':val,'improvement':improvement,
                      'stale':stale,'history':history,'seconds':time.time()}
            (out/f'a0_seed{seed}_progress.json').write_text(json.dumps(progress,indent=2))
            if stale>=3:
                print('EARLY_STOP',seed,epoch,'best_epoch',best_epoch,flush=True)
                break
            # no test-set checks or early selection based on test.
        del model
        model=ViT().to('cuda');model.load_state_dict(state)
        checkpoint=out/f'a0_seed{seed}_best.pt'
        assert not checkpoint.exists()
        torch.save({'model':state,'seed':seed,'selected_epoch':best_epoch,
                    'best_validation_loss':best},checkpoint)
        # Archive on Drive before advancing: VM-local checkpoints are ephemeral.
        import subprocess
        remote=f'gdrive:colab_cache/L26.31/d1b_8c4a04ea/a0_seed{seed}_best.pt'
        subprocess.run(['rclone','copyto',str(checkpoint),remote,'--transfers','1',
                        '--tpslimit','5','--retries','3'],check=True)
        subprocess.run(['rclone','check',str(checkpoint),remote,'--checksum',
                        '--one-way'],check=True)
        print('DRIVE_CHECKPOINT',seed,hashlib.sha256(checkpoint.read_bytes()).hexdigest(),flush=True)
        evaluate(series,model,mean,std,static,'cuda',table,seed,out)
        del model,state;torch.cuda.empty_cache()
    (out/'all.done').write_text(dt.datetime.now().astimezone().isoformat())
    print('ALL_DONE',flush=True)
if __name__=='__main__':main()
