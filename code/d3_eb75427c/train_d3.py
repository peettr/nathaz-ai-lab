"""D3: A0-parity conditional WeatherBench experiment; run only in isolated Colab T4.
Public WeatherBench data; D2 embeddings stay on VM/Drive. No test-based selection.
"""
import argparse, datetime as dt, hashlib, importlib.util, json, math, os, pathlib, random, subprocess, time
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('a0', HERE/'train_a0_resume_v2.py')
a0=importlib.util.module_from_spec(spec);spec.loader.exec_module(a0)
SEEDS=(11,23,37); ARMS=('A1','A2','A3','A4')

class ConditionalViT(a0.ViT):
    def __init__(self):
        super().__init__(conditional=True)
        # Same trainable parameter set in all four arms; A4 uses this constant.
        self.learned_constant=nn.Parameter(torch.zeros(384))
    def forward(self, previous, current, static, condition, arm):
        if arm=='A4': condition=self.learned_constant[None].expand(current.shape[0],-1)
        b=current.shape[0]
        x=torch.cat([previous,current,static.expand(b,-1,-1,-1)],dim=1)
        x=self.patch(x).flatten(2).transpose(1,2)+self.pos
        ctx=self.cond_proj(condition).unsqueeze(1)
        for block,cross in zip(self.blocks,self.cross):
            x=block(x)
            x=x+cross(x,ctx,ctx,need_weights=False)[0]
        x=self.output(self.norm(x)).reshape(b,16,16,5,2,4)
        return x.permute(0,3,1,4,2,5).reshape(b,5,32,64)

class Embeddings:
    def __init__(self,root,mismatch):
        root=pathlib.Path(root)
        files=sorted(root.glob('text_*_embeddings.npz'))
        assert len(files)==115, len(files)
        dates=[];llm=[];template=[]
        for f in files:
            with np.load(f,allow_pickle=False) as z:
                assert set(z.files)=={'initialization','llm','template'}
                dates.extend(z['initialization'].tolist());llm.append(z['llm']);template.append(z['template'])
        self.dates=dates;self.index={d:i for i,d in enumerate(dates)}
        assert len(self.index)==len(dates)==58439 and len(set(dates))==len(dates)
        self.llm=np.concatenate(llm).astype('f4');self.template=np.concatenate(template).astype('f4')
        assert self.llm.shape==self.template.shape==(58439,384)
        assert np.isfinite(self.llm).all() and np.isfinite(self.template).all()
        self.mismatch=json.loads(pathlib.Path(mismatch).read_text())
        assert set(self.mismatch)==set(dates) and set(self.mismatch.values())==set(dates)
        self.bad_index=np.array([self.index[self.mismatch[d]] for d in dates],dtype='i4')
        assert all(abs((dt.datetime.fromisoformat(d)-dt.datetime.fromisoformat(self.mismatch[d])).total_seconds())>=30*86400 for d in dates)
        self.timestamps={}
        for year in range(1979,2019):
            start=dt.datetime(year,1,1)
            self.timestamps[year]=[(start+dt.timedelta(hours=6*i)).isoformat() for i in range(1464 if year%4==0 and (year%100!=0 or year%400==0) else 1460)]
    def vector(self,year,index,arm):
        timestamp=self.timestamps[year][index]
        j=self.index[timestamp]
        if arm=='A2': return self.llm[self.bad_index[j]]
        return self.template[j] if arm=='A3' else self.llm[j]

class ConditionedSamples(Dataset):
    def __init__(self,base,emb,arm):self.base=base;self.emb=emb;self.arm=arm
    def __len__(self):return len(self.base)
    def __getitem__(self,i):
        values=self.base[i];year,step=self.base.keys[i]
        return (*values,torch.from_numpy(self.emb.vector(year,step,self.arm).copy()))

def evaluate(series,model,mean,std,static,emb,arm,seed,table,out):
    model.eval(); weights=np.cos(np.deg2rad(series.lat)).astype('f8')[:,None]
    weights=np.broadcast_to(weights/(weights.sum()*64),(32,64))
    scores={m:{lead:np.zeros(6,dtype='f8') for lead in a0.LEADS} for m in ('vit','persistence','climatology')}
    counts={lead:0 for lead in a0.LEADS}
    with torch.inference_mode():
        for year in (2017,2018):
            n=series.n(year);start=dt.datetime(year,1,1)
            for begin in range(1,n-12,32):
                idx=list(range(begin,min(begin+32,n-12)))
                prev=np.stack([series.frame(year,i-1) for i in idx]);initial=np.stack([series.frame(year,i) for i in idx])
                p=torch.from_numpy((prev-mean)/std).to('cuda');x=torch.from_numpy((initial-mean)/std).to('cuda')
                # Freeze origin t0 condition for ALL autoregressive steps.
                condition=torch.from_numpy(np.stack([emb.vector(year,i,arm) for i in idx])).to('cuda')
                for step in range(1,13):
                    z=model(p,x,static,condition,arm);p,x=x,z
                    if step not in a0.LEADS:continue
                    estimate=z.cpu().numpy()*std+mean
                    for j,i in enumerate(idx):
                        truth=series.frame(year,i+step);valid=start+dt.timedelta(hours=(i+step)*6)
                        a0.score_add(scores['vit'][step],estimate[j],truth,weights)
                        a0.score_add(scores['persistence'][step],initial[j],truth,weights)
                        a0.score_add(scores['climatology'][step],a0.climate_at(table,valid),truth,weights)
                        counts[step]+=1
                if begin%(32*32)==1:print('EVAL',arm,seed,year,begin,n,flush=True)
    assert all(v==2894 for v in counts.values()),counts
    return {'seed':seed,'arm':arm,'test_years':[2017,2018],'counts':counts,'rmse':{
        method:{str(lead):dict(zip(a0.FIELDS+['speed10'],[math.sqrt(v/counts[lead]) for v in scores[method][lead]]))
                for lead in a0.LEADS} for method in scores}}

def hashfile(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def archive(checkpoint,drive):
    remote=f'{drive}/{checkpoint.name}'
    check=subprocess.run(['rclone','lsjson',remote],capture_output=True,text=True)
    if check.returncode: subprocess.run(['rclone','copyto',str(checkpoint),remote,'--transfers','1','--tpslimit','5','--retries','3'],check=True)
    else: assert json.loads(check.stdout)[0]['Size']==checkpoint.stat().st_size
    remote_md5=subprocess.run(['rclone','md5sum',remote],capture_output=True,text=True,check=True).stdout.split()[0].lower()
    assert remote_md5==hashlib.md5(checkpoint.read_bytes()).hexdigest()
    print('DRIVE_VERIFIED',remote,hashfile(checkpoint),flush=True)
    return {'path':remote,'sha256':hashfile(checkpoint)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default='/content/l2631/weatherbench');p.add_argument('--embed',required=True)
    p.add_argument('--mismatch',required=True);p.add_argument('--out',required=True);p.add_argument('--drive',required=True)
    p.add_argument('--arms',nargs='+',default=ARMS);p.add_argument('--seeds',nargs='+',type=int,default=SEEDS)
    p.add_argument('--batch',type=int,default=64);p.add_argument('--epochs',type=int,default=60)
    args=p.parse_args();assert set(args.arms)<=set(ARMS) and set(args.seeds)<=set(SEEDS)
    os.environ['RCLONE_CONFIG']=str(HERE/'rclone.conf')
    assert pathlib.Path(os.environ['RCLONE_CONFIG']).is_file()
    out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(4);assert torch.cuda.get_device_name(0)=='Tesla T4'
    series=a0.Series(args.root);mean,std=a0.training_stats(series);emb=Embeddings(args.embed,args.mismatch)
    static=torch.from_numpy(series.static[None]).to('cuda')
    lat=torch.from_numpy(np.cos(np.deg2rad(series.lat)).astype('f4')[None,None,:,None]).to('cuda')
    table=a0.climate(series);base_train=a0.Samples(series,range(1979,2016),mean,std);base_valid=a0.Samples(series,[2016],mean,std)
    params=sum(p.numel() for p in ConditionalViT().parameters())
    config={'a0_source_sha256':hashfile(HERE/'train_a0_resume_v2.py'),'data':'WeatherBench-v1-5.625deg','split':[1979,2015,2016,2017,2018],
            'gpu':torch.cuda.get_device_name(0),'torch':torch.__version__,'precision':'float32','batch':args.batch,
            'patch':[2,4],'width':320,'blocks':7,'heads':8,'optimizer':'AdamW','lr':0.0003,'weight_decay':0.01,
            'early_stop_relative_improvement':0.005,'early_stop_patience':3,'epochs_max':args.epochs,
            'seeds':list(SEEDS),'arms':list(ARMS),'conditional_parameters':params,'a0_parameters':sum(p.numel() for p in a0.ViT().parameters()),
            'condition':'one 384-d vector per sample, cross-attention in each of 7 blocks; t0 fixed for rollout',
            'embedding_manifest_sha256':hashfile(pathlib.Path(args.embed)/'manifest_final.json'),
            'mismatch_sha256':hashfile(args.mismatch),'mean':mean[:,0,0].tolist(),'std':std[:,0,0].tolist()}
    cfg=out/'config.json'
    if cfg.exists():assert json.loads(cfg.read_text())==config
    else: cfg.write_text(json.dumps(config,indent=2))
    print('CONFIG',json.dumps({'gpu':config['gpu'],'params':params,'train':len(base_train),'valid':len(base_valid)}),flush=True)
    for arm in args.arms:
      train=ConditionedSamples(base_train,emb,arm);valid=ConditionedSamples(base_valid,emb,arm)
      loader=DataLoader(train,batch_size=args.batch,shuffle=True,num_workers=2,pin_memory=True)
      vloader=DataLoader(valid,batch_size=args.batch,num_workers=2,pin_memory=True)
      for seed in args.seeds:
        prefix=f'{arm.lower()}_seed{seed}';metrics=out/(prefix+'_metrics.json');checkpoint=out/(prefix+'_best.pt')
        if metrics.exists() and checkpoint.exists():
            print('SKIP_COMPLETE',prefix,flush=True);continue
        if checkpoint.exists():
            saved=torch.load(checkpoint,map_location='cpu',weights_only=False)
            assert saved['arm']==arm and saved['seed']==seed
            model=ConditionalViT().to('cuda');model.load_state_dict(saved['model'])
            print('RESUME_SELECTED',prefix,saved['selected_epoch'],flush=True)
        else:
            random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
            model=ConditionalViT().to('cuda');opt=torch.optim.AdamW(model.parameters(),lr=0.0003,weight_decay=0.01)
            best=float('inf');best_epoch=0;stale=0;history=[]
            for epoch in range(1,args.epochs+1):
                t0=time.monotonic();model.train();losses=[]
                for previous,current,target,condition in loader:
                    previous=previous.to('cuda',non_blocking=True);current=current.to('cuda',non_blocking=True)
                    target=target.to('cuda',non_blocking=True);condition=condition.to('cuda',non_blocking=True)
                    pred=model(previous,current,static,condition,arm)
                    loss=(((pred.float()-target)**2)*lat).mean()
                    opt.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(model.parameters(),1.0);opt.step();losses.append(loss.item())
                model.eval();vsum=0.;vn=0
                with torch.inference_mode():
                    for previous,current,target,condition in vloader:
                        pred=model(previous.to('cuda'),current.to('cuda'),static,condition.to('cuda'),arm).float()
                        err=((pred-target.to('cuda'))**2*lat).mean(dim=(1,2,3))
                        vsum+=float(err.sum());vn+=len(err)
                val=vsum/vn
                print('EPOCH',prefix,epoch,'train',float(np.mean(losses)),'val',val,'seconds',round(time.monotonic()-t0,1),flush=True)
                if val<best:
                    best=val;best_epoch=epoch
                    state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
                prev=history[-1] if history else float('inf')
                improvement=(prev-val)/prev if history else float('inf')
                history.append(val);stale=stale+1 if improvement<0.005 else 0
                (out/(prefix+'_progress.json')).write_text(json.dumps({'arm':arm,'seed':seed,'epoch':epoch,'best_epoch':best_epoch,'best_val':best,'history':history,'stale':stale,'time':time.time()}))
                if stale>=3:
                    print('EARLY_STOP',prefix,epoch,'best_epoch',best_epoch,flush=True);break
            del model
            model=ConditionalViT().to('cuda');model.load_state_dict(state)
            assert not checkpoint.exists()
            torch.save({'model':state,'seed':seed,'arm':arm,'selected_epoch':best_epoch,'best_validation_loss':best},checkpoint)
        archive(checkpoint,args.drive)
        if not metrics.exists():
            result=evaluate(series,model,mean,std,static,emb,arm,seed,table,out)
            metrics.write_text(json.dumps(result,indent=2))
            print('SCORED',prefix,hashfile(metrics),flush=True)
        archive(metrics,args.drive)
        del model;torch.cuda.empty_cache()
    if len(args.arms)==4 and len(args.seeds)==3:
        assert len(list(out.glob('a?_seed??_metrics.json')))==12
        (out/'all.done').write_text(dt.datetime.now().astimezone().isoformat())
        print('ALL_DONE',flush=True)
if __name__=='__main__':main()
