# 用法: python run.py short | python run.py full EPOCH_TR EPOCH_FNO BUDGET_MIN
import sys,time,json,math
sys.path.insert(0,'/content/code')
import numpy as np,torch
from common import *
from models import *
MODE=sys.argv[1]; T0=time.time(); torch.manual_seed(0); np.random.seed(0)
def log(*a): print(f'[{time.time()-T0:7.0f}s]',*a,flush=True)
runs={k:load(k) for k in TRAIN+VAL+TEST+CEIL}; n=fit_norm(runs); X,Nm,tapids=points(); assert list(runs['v7']['tap_cols'])==tapids
E=torch.tensor(np.c_[X,Nm],device=dev)
Ytr=np.concatenate([runs[k]['cp'][runs[k]['idx']] for k in TRAIN]); Ytr=(Ytr-n.ym)/n.ys
Xtr=np.concatenate([hist_feat(runs[k],n,runs[k]['idx']) for k in TRAIN]).astype('f4')
Xva=hist_feat(runs['P303_pre'],n,runs['P303_pre']['idx']).astype('f4'); Yva_cp=runs['P303_pre']['cp'][runs['P303_pre']['idx']]
log('train frames',len(Xtr),'val',len(Xva),'feat',Xtr.shape[1])
# PCA 只在训练组拟合
Xt=torch.tensor(Xtr,device=dev,dtype=torch.float64); C=Xt.T@Xt; w,V=torch.linalg.eigh(C)
def mk_pf(k):
    W_=V[:,-k:].flip(1).float(); S_=(Xt.float()@W_).std(0); log(f'PCA{k} 方差占比',float(w[-k:].sum()/w.sum()))
    return lambda A:(torch.tensor(A,device=dev)@W_/S_).cpu()
pf=mk_pf(64); Ftr=pf(Xtr); Fva=pf(Xva); Ytrt=torch.tensor(Ytr)
Str=torch.tensor(np.concatenate([seq(runs[k],n,runs[k]['idx']) for k in TRAIN]).astype('f4')); Sva=torch.tensor(seq(runs['P303_pre'],n,runs['P303_pre']['idx']).astype('f4'))
def va_rmse(P): e,c=rmse_corr(P*n.ys+n.ym,Yva_cp); return float(e.mean()),float(c.mean())
def train_tr(steps_limit=None,epochs=1,deadline=None,k=64,h=128,tag='tr'):
    m=tr_model(k,h); log('Transolver',k,h,'params',sum(p.numel() for p in m.parameters()))
    opt=torch.optim.AdamW(m.parameters(),1e-3,weight_decay=1e-4); bs=8; npts=2048; N=len(Ftr); per=N//bs; total=per*epochs; sch=torch.optim.lr_scheduler.OneCycleLR(opt,1e-3,total_steps=max(total,steps_limit or 1))
    best=(9e9,None,-1); step=0; hist=[]; t0=time.time(); ts=[]
    for ep in range(epochs):
        m.train(); perm=torch.randperm(N); L=0.
        for b in range(per):
            I=perm[b*bs:(b+1)*bs]; pts=torch.randperm(8040,device=dev)[:npts]
            f=Ftr[I].to(dev); y=Ytrt[I].to(dev)[:,pts]; fx=f[:,None,:].expand(-1,npts,-1); e=E[pts][None].expand(bs,-1,-1)
            t1=time.time(); opt.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.bfloat16): loss=((m(fx,embedding=e)[...,0].float()-y)**2).mean()
            assert torch.isfinite(loss),'NaN loss'
            loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(),1.); opt.step(); sch.step(); torch.cuda.synchronize(); ts.append(time.time()-t1); L+=loss.item(); step+=1
            if steps_limit and step>=steps_limit: return m,dict(sec_per_step=float(np.median(ts[10:])),steps=step,last_loss=loss.item())
        va=va_rmse(tr_pred(m,Fva,E)); hist.append((ep,L/per,*va,time.time()-t0)); log(tag,'ep',ep,'loss',round(L/per,4),'val rmse,corr',va)
        json.dump(hist,open(f'{OUT}/{tag}_hist.json','w'))
        if va[0]<best[0]: best=(va[0],{k:v.detach().cpu().clone() for k,v in m.state_dict().items()},ep); torch.save(best[1],f'{OUT}/{tag}_best.pt')
        if deadline and time.time()>deadline: log('到时间上限，停止于 ep',ep); break
    m.load_state_dict(best[1]); return m,dict(best_val_rmse=best[0],best_epoch=best[2],epochs_done=len(hist),steps=step,hist=hist)
def train_fno(steps_limit=None,epochs=1,deadline=None):
    m=fno_model(); log('FNO params',sum(p.numel() for p in m.parameters()))
    opt=torch.optim.AdamW(m.parameters(),1e-3,weight_decay=1e-4); bs=32; N=len(Str); per=N//bs; total=per*epochs; sch=torch.optim.lr_scheduler.OneCycleLR(opt,1e-3,total_steps=max(total,steps_limit or 1))
    best=(9e9,None,-1); step=0; hist=[]; t0=time.time(); ts=[]
    for ep in range(epochs):
        m.train(); perm=torch.randperm(N); L=0.
        for b in range(per):
            I=perm[b*bs:(b+1)*bs]; s=Str[I].to(dev); y=Ytrt[I].to(dev); t1=time.time(); opt.zero_grad(set_to_none=True)
            loss=((m(s)[:,:,-1]-y)**2).mean()  # FFT 不支持 bf16，FNO 用 float32
            assert torch.isfinite(loss),'NaN loss'
            loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(),1.); opt.step(); sch.step(); torch.cuda.synchronize(); ts.append(time.time()-t1); L+=loss.item(); step+=1
            if steps_limit and step>=steps_limit: return m,dict(sec_per_step=float(np.median(ts[10:])),steps=step,last_loss=loss.item())
        va=va_rmse(fno_pred(m,Sva)); hist.append((ep,L/per,*va,time.time()-t0)); log('FNO ep',ep,'loss',round(L/per,4),'val rmse,corr',va)
        json.dump(hist,open(f'{OUT}/fno_hist.json','w'))
        if va[0]<best[0]: best=(va[0],{k:v.detach().cpu().clone() for k,v in m.state_dict().items()},ep); torch.save(best[1],f'{OUT}/fno_best.pt')
        if deadline and time.time()>deadline: log('到时间上限，停止于 ep',ep); break
    m.load_state_dict(best[1]); return m,dict(best_epoch=best[2],epochs_done=len(hist),steps=step,hist=hist)
if MODE=='short':
    t=time.time(); _,a=train_tr(steps_limit=60); log('TR short',a)
    m=tr_model(); t=time.time(); tr_pred(m,Fva,E); ev_tr=time.time()-t; log('TR val eval sec',ev_tr,'frames',len(Fva))
    _,b=train_fno(steps_limit=60); log('FNO short',b)
    m=fno_model(); t=time.time(); fno_pred(m,Sva); ev_f=time.time()-t
    json.dump(dict(tr=a,fno=b,ev_tr=ev_tr,ev_fno=ev_f,n_train=len(Ftr),val=len(Fva),setup_sec=None,gpu=torch.cuda.get_device_name(0),per_tr=len(Ftr)//8,per_fno=len(Str)//32),open(f'{OUT}/short.json','w'),indent=1); log('SHORT DONE'); open('/content/short.done','w').write('1'); sys.exit(0)
# ---- full ----
ETR,EF,BM=int(sys.argv[2]),int(sys.argv[3]),float(sys.argv[4]); DL=T0+BM*60
info={}
# 基线 2 岭回归（只用训练+验证选 alpha）
Yt=torch.tensor(Ytr,device=dev,dtype=torch.float64); XtY=Xt.T@Yt; ev,EV=w,V.clone(); Xv=torch.tensor(Xva,device=dev,dtype=torch.float64); Pj=EV.T@XtY; best=(9e9,None)
for al in [1e1,1e2,1e3,1e4,1e5,1e6,1e7]:
    B=EV@(Pj/(ev+al)[:,None]); v=va_rmse((Xv@B).cpu().numpy().astype('f4')); log('ridge',al,v)
    if v[0]<best[0]: best=(v[0],al,B.float())
RB=best[2]; info['ridge_alpha']=best[1]; info['ridge_val_rmse']=best[0]; del XtY,Pj
info['tr_grid']={}; bestc=None
for k_,h_ in ((64,128),(256,128),(256,256)):
    pf=mk_pf(k_); Ftr=pf(Xtr); Fva=pf(Xva); tag=f'tr_{k_}_{h_}'
    m_,i_=train_tr(epochs=ETR,deadline=time.time()+BM*60/4,k=k_,h=h_,tag=tag); info['tr_grid'][tag]=i_; log(tag,'best val',i_['best_val_rmse'],'ep',i_['best_epoch'])
    if bestc is None or i_['best_val_rmse']<bestc[0]: bestc=(i_['best_val_rmse'],m_,pf,Fva,tag)
_,mTr,pf,Fva,info['tr_selected']=bestc; log('选定',info['tr_selected'])
mF,iF=train_fno(epochs=EF,deadline=time.time()+BM*60/5); info['fno']={k:v for k,v in iF.items()}
# ---- 到此为止不看留出；下面才算留出 ----
t=runs['A1_101']; idx=t['idx']; Xte=hist_feat(t,n,idx).astype('f4'); y=t['cp'][idx]; Fte=pf(Xte); Ste=torch.tensor(seq(t,n,idx).astype('f4')); assert len(idx)>=2100
log('test frames',len(idx),'t',t['t'][idx[0]],t['t'][idx[-1]])
torch.cuda.synchronize(); s=time.time(); pT=tr_pred(mTr,Fte,E); torch.cuda.synchronize(); info['infer_tr_sec']=time.time()-s
s=time.time(); pF=fno_pred(mF,Ste); torch.cuda.synchronize(); info['infer_fno_sec']=time.time()-s
pT=pT*n.ys+n.ym; pF=pF*n.ys+n.ym; pR=(torch.tensor(Xte,device=dev)@RB).cpu().numpy()*n.ys+n.ym
# 基线 1 准定常：滞后按验证组选
vr=runs['P303_pre']; L=[(rmse_corr(n.ym[None]*vr['r'][vr['idx']-l,None],Yva_cp)[0].mean(),l) for l in range(0,41)]; lag=min(L)[1]; info['qs_lag_frames']=int(lag)
pQ0=n.ym[None]*t['r'][idx,None]; pQL=n.ym[None]*t['r'][idx-lag,None]; pM=np.broadcast_to(n.ym,y.shape)
# 残差方差由验证组标定
V=dict(T=tr_pred(mTr,Fva,E)*n.ys+n.ym,F=fno_pred(mF,Sva)*n.ys+n.ym,R=(torch.tensor(Xva,device=dev)@RB).cpu().numpy()*n.ys+n.ym)
sig={k:(v-Yva_cp).std(0) for k,v in V.items()}
# 去相关时间（只用训练）
cpv=runs['v7']['cp'][runs['v7']['idx']]; cpv=cpv-cpv.mean(0); dec=[]
for j in range(0,8040,40):
    a=np.correlate(cpv[:,j],cpv[:,j],'full')[len(cpv)-1:]; a=a/a[0]; dec.append(np.argmax(a<1/np.e)/5.)
info['decor_s_median']=float(np.median(dec)); B_FR=150; bl=150*max(1,math.ceil(info['decor_s_median']/30)); nb=len(idx)//bl; info['block_frames']=bl; info['n_blocks']=nb; y=y[:nb*bl]
M=dict(transolver=pT,fno=pF,ridge=pR,qs0=pQ0,qslag=pQL,mean=pM)
SETS=dict(taps=np.arange(8000,8040),surface=np.arange(0,8000))
def blocksum(p,S,d='cuda'):
    a=torch.tensor(p[:nb*bl][:,S],device=d,dtype=torch.float64); b=torch.tensor(y[:,S],device=d,dtype=torch.float64); r=[]
    for k in range(nb):
        i=torch.arange(k*bl,(k+1)*bl); A,Bb=a[i],b[i]; r.append(torch.stack([(A-Bb).pow(2).sum(0),A.sum(0),Bb.sum(0),(A*Bb).sum(0),(A*A).sum(0),(Bb*Bb).sum(0)]))
    return torch.stack(r)  # nb,6,P
def stats(sm,wt):
    # sm nb,6,P ; wt R,nb
    s=torch.einsum('rb,b6p->r6p'.replace('6','k'),wt,sm); N=wt.sum(1,keepdim=True)*bl
    e=torch.sqrt(s[:,0]/N).mean(1); ax,ay,xy,xx,yy=s[:,1],s[:,2],s[:,3],s[:,4],s[:,5]; c=((xy-ax*ay/N)/torch.sqrt((xx-ax*ax/N).clamp_min(1e-20)*(yy-ay*ay/N).clamp_min(1e-20))).mean(1); return e,c
res={}; g=torch.Generator(device='cuda').manual_seed(0); W=torch.multinomial(torch.ones(nb,device=dev)/nb,nb*20000,True,generator=g).reshape(20000,nb); WT=torch.zeros(20000,nb,device=dev,dtype=torch.float64).scatter_add_(1,W,torch.ones_like(W,dtype=torch.float64))
for sn,S in SETS.items():
    BS={k:blocksum(p,S) for k,p in M.items()}; one=torch.ones(1,nb,device=dev,dtype=torch.float64); base={k:[float(x) for x in stats(v,one)] if k!='mean' else [float(stats(v,one)[0]),None] for k,v in BS.items()}; res[sn]=dict(point=base)
    for mdl in ('transolver','fno'):
        for bl_name in ('qs0','qslag','ridge'):
            E1=[];E2=[];C1=[];C2=[]
            for i in range(0,20000,500):
                a,b=stats(BS[mdl],WT[i:i+500]); c,d=stats(BS[bl_name],WT[i:i+500]); E1.append(a);E2.append(c);C1.append(b);C2.append(d)
            e1,e2,c1,c2=map(torch.cat,(E1,E2,C1,C2)); dr=(e2-e1)/e2; dc=c1-c2
            pa,pb=stats(BS[mdl],one); qa,qb=stats(BS[bl_name],one); rr=float((qa-pa)/qa); cc=float(pb-qb)
            ci=lambda z:[float(torch.quantile(z.float(),.025)),float(torch.quantile(z.float(),.975))]
            win=(rr>=.05) and ci(dr)[0]>0 and (cc>=.02) and ci(dc)[0]>0
            res[sn][f'{mdl}_vs_{bl_name}']=dict(rmse_reduction=rr,rmse_ci=ci(dr),corr_gain=cc,corr_ci=ci(dc),win=bool(win))
    Ceil={}
    for c in CEIL:
        cc=runs[c]['cp'][runs[c]['idx']][:nb*bl]; e,co=rmse_corr(cc[:,S],y[:,S]); Ceil[c]=dict(rmse=float(e.mean()),corr=float(co.mean()))
    res[sn]['ceiling_same_inflow']=Ceil
    # 只描述：时均 Cp、Cp'（0-1 Hz 带内）、峰值
    desc={}
    for k,p in M.items():
        q=p[:nb*bl][:,S]; yy=y[:,S]
        desc[k]=dict(meanCp_rmse=float(np.sqrt(((q.mean(0)-yy.mean(0))**2).mean())),cpp_low_rmse=float(np.sqrt(((q.std(0)-yy.std(0))**2).mean())),cpp_low_ratio=float(q.std(0).mean()/yy.std(0).mean()),peakmin_mae=float(np.abs(q.min(0)-yy.min(0)).mean()),peakmax_mae=float(np.abs(q.max(0)-yy.max(0)).mean()))
    desc['truth']=dict(meanCp_abs=float(np.abs(y[:,S].mean(0)).mean()),cpp_low=float(y[:,S].std(0).mean()),cpp_full_4165=float(t['prime_full'][S].mean())); res[sn]['describe']=desc
    # 可靠性，按时间块
    rel={}
    for k,key in (('transolver','T'),('fno','F'),('ridge','R')):
        s=sig[key][S]; z=(M[k][:nb*bl][:,S]-y[:,S])/s; bl_c=[float((np.abs(z[j*bl:(j+1)*bl])<=1.96).mean()) for j in range(nb)]
        rel[k]=dict(cover95=float(np.mean(bl_c)),cover95_min=float(np.min(bl_c)),cover95_max=float(np.max(bl_c)),z_rms=float(np.sqrt((z**2).mean())))
    res[sn]['reliability']=rel
res['pass_transolver']=all(res[s][f'transolver_vs_{b}']['win'] for s in SETS for b in ('qs0','qslag','ridge'))
res['pass_fno']=all(res[s][f'fno_vs_{b}']['win'] for s in SETS for b in ('qs0','qslag','ridge'))
info['nan_preds']={k:int(np.isnan(v).sum()) for k,v in M.items()}
lbm=420./642*5.2*3600; info['infer_ratio_tr_to_lbm']=info['infer_tr_sec']/lbm; info['lbm_sec_for_420s']=lbm; info['wall_sec']=time.time()-T0
json.dump(dict(info=info,res=res),open(f'{OUT}/metrics.json','w'),indent=1,ensure_ascii=False)
np.savez_compressed(f'{OUT}/preds_taps.npz',y=y[:,8000:].astype('f4'),**{k:v[:nb*bl][:,8000:].astype('f4') for k,v in M.items()},t=t['t'][idx[:nb*bl]])
log('FULL DONE pass_tr',res['pass_transolver'],'pass_fno',res['pass_fno']); open('/content/run.done','w').write('1')
