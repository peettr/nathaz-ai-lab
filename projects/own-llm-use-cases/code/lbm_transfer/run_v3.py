#!/usr/bin/env python3
"""Upstream-only Silsoe v7 input ablation; never writes source inputs.
python run_v3.py --input <local CSV copy> --out <lab output folder>
All outputs have _v3 suffix; refuses overwrite. CPU PyTorch, numpy, scipy, matplotlib.
"""
import argparse,csv,json,hashlib,sys,time
from pathlib import Path
import numpy as np
from scipy.signal import welch
import scipy.linalg as la
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import torch
from torch import nn
from numpy.lib.stride_tricks import sliding_window_view

TAPS=[f'V{i}' for i in range(2,7)]+[f'H{i}' for i in range(1,7)]
RACK=[f'R_y{y}_z{z}' for z in (1,3,6,12) for y in (-12,-6,0,6,12)]
UPSTREAM=[f'P_x{x}_z{z}' for z in (1,3,6,12) for x in ('-33.05','-30.00','-25.00','-20.00','-15.00','-10.00','-5.00','0.00')]
B1=[p for p in UPSTREAM if int(p.rsplit('_z',1)[1]) in (1,3,6) and float(p.split('_z')[0].split('P_x')[1])<=-10]
B2=[p for p in B1 if float(p.split('_z')[0].split('P_x')[1])<=-15]
FS=50; LAGS=np.arange(61)*5 # 0..6 s at 0.1s spacing
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run import read_csv,score

def load(root):
    prefixes=RACK+B1
    pc=['step','t_s']+[f'{p}_{c}' for p in prefixes for c in ('ux','uy','uz')]+['REF_rho','REF_ux','REF_uy','REF_uz']
    tc=['step','t_s']+TAPS
    taps=np.concatenate([read_csv(root/f'S600v7_seg{s}_taps.csv',tc) for s in (1,2)])
    probes=np.concatenate([read_csv(root/f'S600v7_seg{s}_probes.csv',pc) for s in (1,2)])
    if len(taps)!=32100 or not np.array_equal(taps[:,0],probes[:,0]) or not np.all(np.diff(taps[:,0])==16):raise ValueError('cadence/seam mismatch')
    r=probes[:,pc.index('REF_rho')]; cs=np.r_[0.,np.cumsum(r)]; idx=np.arange(len(r));lo=np.maximum(0,idx-99)
    smooth=(cs[idx+1]-cs[lo])/(idx-lo+1)
    keep=taps[:,1]>=42;t=taps[keep,1];p=probes[keep];tp=taps[keep];ref=smooth[keep]
    if len(t)!=30001 or np.max(abs(t-tp[:,0]*.00125))>1e-4:raise ValueError('time mismatch')
    train=t<462;rv=p[:,[pc.index('REF_'+c) for c in ('ux','uy','uz')]]
    q=np.mean(.5*p[train,pc.index('REF_rho')]*np.sum(rv[train]**2,axis=1))
    y=(tp[:,2:]-ref[:,None])/(3*q)
    x=p[:,[pc.index(f'{v}_{c}') for v in prefixes for c in ('ux','uy','uz')]].reshape(-1,len(prefixes),3)
    return t,x[:,:20].reshape(-1,60),x[:,20:].reshape(-1,len(B1)*3),y,q

class CNN(nn.Module):
    def __init__(self,c):
        super().__init__();layers=[]
        for i,d in enumerate((1,2,4,8)):
            layers += [nn.ConstantPad1d((4*d,0),0),nn.Conv1d(c if i==0 else 32,32,5,dilation=d),nn.ReLU()]
        self.net=nn.Sequential(*layers);self.head=nn.Sequential(nn.Linear(32,48),nn.ReLU(),nn.Linear(48,11))
    def forward(self,x):return self.head(self.net(x)[:,:,-1])

def make_windows(x,ids):
    # causal, exactly 0..6s in 0.1s steps; result samples x channels x 61
    z=np.stack([x[ids-k] for k in LAGS],axis=2).astype('float32')
    return torch.from_numpy(z)

def fit_family(name,x,y,t,stations):
    ids=np.arange(300,len(t))
    tr=ids[(t[ids]<462)&(ids%5==0)]
    va=ids[(t[ids]>=462)&(t[ids]<522)&(ids%5==0)]
    te=ids[t[ids]>=522]
    # Quasi-steady: choose strictly nonnegative delay on validation using training-fixed Cp_mean and U.
    # Station at z3 matches independent lead diagnostic; upstream uses x=-10m z3.
    qs_name='R_y0_z3' if name=='A' else ('P_x-10.00_z3' if name=='B1' else 'P_x-15.00_z3')
    station=stations.index(qs_name)
    u=x[:,3*station+2];U=u[tr].mean();cpmean=y[tr].mean(axis=0)
    qs_errors=[]
    for lag in LAGS:
        pred=cpmean[None,:]*(u[va-lag,None]*abs(u[va-lag,None]))/(U*abs(U))
        qs_errors.append(np.sqrt(np.mean((pred-y[va])**2)))
    lag=int(LAGS[np.argmin(qs_errors)])
    qs=cpmean[None,:]*(u[te-lag,None]*abs(u[te-lag,None]))/(U*abs(U))
    print(name,'quasisteady lag s',lag/FS,'val',min(qs_errors),flush=True)
    # FIR: fit PCA of standardized instantaneous spatial velocity, strictly train-only;
    # 12 PCs ensure ridge is feasible with 61 physical lags on modest CPU. Full 0..6s history retained.
    xm=x[tr].mean(0);xs=np.maximum(x[tr].std(0),1e-8)
    X=((x-xm)/xs).astype('float32');_,_,vt=np.linalg.svd(X[tr],full_matrices=False)
    basis=vt[:min(12,x.shape[1])].T;Z=X@basis
    def design(sel):return np.concatenate([Z[sel-k] for k in LAGS],axis=1).astype('float64')
    Ftr=design(tr);Fv=design(va);Fte=design(te)
    fm=Ftr.mean(0);fs=np.maximum(Ftr.std(0),1e-8);D=(Ftr-fm)/fs;Ymean=y[tr].mean(0)
    gram=D.T@D;rhs=D.T@(y[tr]-Ymean);alpha_grid=(100.,1000.,10000.)
    options=[]
    for alpha in alpha_grid:
        coef=la.solve(gram+alpha*np.eye(gram.shape[0]),rhs,assume_a='pos')
        pv=((Fv-fm)/fs)@coef+Ymean
        val=np.sqrt(np.mean((pv-y[va])**2));options.append((val,alpha,coef))
    val,alpha,coef=min(options,key=lambda z:z[0]);fir=((Fte-fm)/fs)@coef+Ymean
    print(name,'FIR alpha',alpha,'val',val,'PCA',basis.shape[1],flush=True)
    # Small causal 1D CNN receives same exactly 0..6s window at 10Hz lag grid.
    ym=y[tr].mean(0);ys=np.maximum(y[tr].std(0),1e-6)
    Wtr=make_windows(X,tr);Wva=make_windows(X,va);Wte=make_windows(X,te)
    Ztr=torch.from_numpy(((y[tr]-ym)/ys).astype('float32'))
    model=CNN(x.shape[1]);opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01)
    best=float('inf');state=None;best_ep=None;patience=0
    for ep in range(1,31):
        model.train();order=torch.randperm(len(tr))
        for batch in order.split(128):
            pred=model(Wtr[batch]);loss=((pred-Ztr[batch])**2).mean()
            opt.zero_grad();loss.backward();opt.step()
        model.eval()
        with torch.no_grad(): p=np.concatenate([model(b).numpy() for b in Wva.split(256)])*ys+ym
        e=float(np.sqrt(np.mean((p-y[va])**2)))
        print(name,'CNN ep',ep,'val',e,flush=True)
        if e<best-1e-5:best=e;best_ep=ep;state={k:v.detach().clone() for k,v in model.state_dict().items()};patience=0
        else:patience+=1
        if patience>=5:break
    model.load_state_dict(state);model.eval()
    with torch.no_grad():cnn=np.concatenate([model(b).numpy() for b in Wte.split(256)])*ys+ym
    print(name,'CNN selected',best_ep,best,flush=True)
    info={'input':name,'stations':stations,'n_spatial_points':x.shape[1]//3,'train_samples':len(tr),'validation_samples':len(va),'test_samples':len(te),'qs_U_training':float(U),'qs_station':qs_name, 'qs_lag_s':lag/FS,'qs_lag_validation_rmse':float(min(qs_errors)),'fir_pca_components':basis.shape[1],'fir_ridge_alpha':alpha,'fir_val_rmse':float(val),'fir_grid_validation_rmse':{str(a):float(v) for v,a,_ in options},'cnn_best_epoch':best_ep,'cnn_val_rmse':best}
    return te,{'quasi_steady':qs,'linear_FIR':fir,'CNN':cnn},info

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);a=parser.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    names=['results_v3.md','metrics_v3.json','timeseries_v3.png','spectrum_v3.png']
    if any((a.out/n).exists() for n in names):raise FileExistsError('v3 outputs already exist')
    start=time.monotonic();torch.set_num_threads(3);np.random.seed(13);torch.manual_seed(13)
    t,xa,xb,y,q=load(a.input);print('loaded',len(t),'q',q,'shapes',xa.shape,xb.shape,flush=True)
    data={};predictions={}
    for key,stations,x in [('B1',B1,xb),('B2',B2,xb.reshape(-1,len(B1),3)[:,[B1.index(s) for s in B2],:].reshape(-1,len(B2)*3))]:
        te,pred,info=fit_family(key,x,y,t,stations)
        data[key]={'setup':info,'metrics':{k:score(y[te],v) for k,v in pred.items()}}
        lm=data[key]['metrics']['linear_FIR'];m=data[key]['metrics']['CNN']
        data[key]['decision']={'mean_rmse_gain_fraction':float(1-m['mean_tap_rmse']/lm['mean_tap_rmse']),'tap_wins':int(np.sum(np.array(m['rmse'])<np.array(lm['rmse'])))}
        predictions[key]=pred
    out={'source':'Silsoe LBM-LES v7 single realization; not measured field pressure','window_s':[42,642],'splits_s':{'train':[42,462],'validation':[462,522],'test':[522,642]},'sampling_Hz':50,'history_lags_s':(LAGS/FS).tolist(),'q_lattice_train_only':float(q),'Cp_definition':'(rho_tap - causal previous/current 100 samples mean rho_REF)/(3*q_train)','runtime_s':time.monotonic()-start,'families':data}
    (a.out/'metrics_v3.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    j=TAPS.index('V2');sel=np.arange(min(len(te),1000))
    fig,axs=plt.subplots(2,1,figsize=(12,8),layout='constrained')
    for ax,(key,preds) in zip(axs,predictions.items()):
        ax.plot(t[te[sel]],y[te[sel],j],label='LBM target',lw=.9)
        for k,v in preds.items():ax.plot(t[te[sel]],v[sel,j],label=k,lw=.9,alpha=.8)
        ax.set(title=f'{key}: V2, first 20 s of test',ylabel='Cp');ax.legend(ncol=4,fontsize=8)
    axs[-1].set_xlabel('physical time s');fig.savefig(a.out/'timeseries_v3.png',dpi=150);plt.close(fig)
    fig,axs=plt.subplots(2,1,figsize=(10,8),layout='constrained')
    for ax,(key,preds) in zip(axs,predictions.items()):
        f,s=welch(y[te,j],fs=FS,nperseg=2048);ax.semilogy(f,s,label='LBM target',lw=1.7)
        for k,v in preds.items():_,s=welch(v[:,j],fs=FS,nperseg=2048);ax.semilogy(f,s,label=k)
        ax.set(xlim=(.1,5),ylabel='Cp²/Hz',title=f'{key}: V2 test PSD, Welch 2048 / 50% overlap');ax.grid(alpha=.3);ax.legend(fontsize=8)
    axs[-1].set_xlabel('Hz');fig.savefig(a.out/'spectrum_v3.png',dpi=150);plt.close(fig)
    lines=['# Silsoe v7：仅真正上游探针的入流→迎风风压试验','',
      '单次 LBM-LES、单一立方体、正迎风，11 个迎风测点。目标是 LBM 时程，不是现场实测 Cp(t)；仅迎风平均 Cp 经现场测量有条件核验。',
      '原始 CSV 只读，复制到本地临时目录运行；42–642 s 50 Hz，训练 42–462 s、验证 462–522 s、测试 522–642 s；非随机时间分割。42–48 s 只作因果历史，实际拟合 48–462 s（10 Hz，4140 点）；验证 462–522 s 为 10 Hz（600 点），测试 522–642 s 保留 50 Hz（6001 点）；所有窗口只包含当前与过去 0–6 s。',
      f'Cp=(ρ_tap−因果 2 s REF ρ 均值)/(3q)，q=训练时段 REF 的 0.5ρ|u|² 均值={q:.8g} 格子单位。参考速度 U_ref 为对应准定常站点的训练均值 uz，u|u|/(U_ref|U_ref|)；时滞 0–6 s 每 0.1 s 验证集选择。',
      'B1：x≤−10 m、z1/z3/z6，共 18 点×3 分量；B2：x≤−15 m、z1/z3/z6，共 15 点×3 分量。严格排除 x=−5/0 及 z12。准定常 B1 用 P_x-10.00_z3，B2 因禁用 −10 m 而改用 P_x-15.00_z3；两者时滞均只在验证段选。FIR 使用训练段标准化、训练段空间 PCA 12 维、全部 61 个 0–6 s 滞后，岭惩罚由验证集 100/1000/10000 三选一；CNN 直接用全部空间分量，因果四层膨胀卷积，用验证集早停。测试集不参与模型选择。',
      '持续性仅用于提前 Δ 的风压预测，这里为同一时刻上游入流预测风压，故不适用。',
      '', '| 输入 | 方法 | 11 点等权 RMSE Cp | 相关系数均值 | 脉动标准差比均值 | 最小 Cp 绝对误差均值 | 最大 Cp 绝对误差均值 |', '|---|---|---:|---:|---:|---:|---:|']
    for key,v in data.items():
        for name,m in v['metrics'].items():lines.append(f"| {key} | {name} | {m['mean_tap_rmse']:.4f} | {m['mean_tap_corr']:.3f} | {m['mean_tap_std_ratio']:.3f} | {m['mean_abs_peak_min_error']:.3f} | {m['mean_abs_peak_max_error']:.3f} |")
    lines+=['','实际探针：']
    for key,stations in [('B1',B1),('B2',B2)]:lines.append(f'{key}（{len(stations)} 点）：'+', '.join(stations)+'。')
    lines+=['','判据：CNN 相对同输入线性 FIR 的 11 测点等权 RMSE 降低至少 20%，且至少 8/11 测点改善，才算“明显好过”。']
    for key,v in data.items():
        s=v['setup'];d=v['decision'];verdict='明显好过' if d['mean_rmse_gain_fraction']>=.2 and d['tap_wins']>=8 else ('差不多（未达明显好过）' if d['mean_rmse_gain_fraction']>=0 else '更差')
        lines.append(f"{key}：准定常站点 {s['qs_station']}，U_ref={s['qs_U_training']:.7g}，验证选滞后 {s['qs_lag_s']:.1f} s；FIR 岭 {s['fir_ridge_alpha']:.0f}，CNN epoch {s['cnn_best_epoch']}；CNN 相对 FIR RMSE 改善 {d['mean_rmse_gain_fraction']:.1%}、胜 {d['tap_wins']}/11，{verdict}。")
    lines+=['','逐点 RMSE、相关、标准差比、检验段局部最小/最大 Cp 有符号峰误差，以及验证选择见 `metrics_v3.json`。时间图 `timeseries_v3.png`，Welch 0.1–5 Hz 谱 `spectrum_v3.png`；频谱高频拟合差时，不应仅凭 RMSE 宣称重建脉动。',
       '先前 `lead_lag_check.md` 的 +4 s/+1.2 s 是 seg2 低通互相关线索，并非本试验测试段选取的时滞；这里所有时滞/模型选择仅用验证段。',
       '数据限制：`21_Digital_Wind_Tunnel/04_Decisions/LBMPV_v7_Acceptance_Verdict_20261013.md:9–19`；2 s 参考平滑：`21_Digital_Wind_Tunnel/04_Decisions/LBMPV_Diag_r1_Verdict_20261013.md:11–24,39–40`。文献评价口径：`16_PETW/05_Literature_Wiki/wiki/liang2_shared_library/sources/NF6S3H9N.md` PDF pp.1–3（LES 输出并非实验真值）。本试验比较结论无文献依据，基于本线数据。',
       f'运行耗时 {out["runtime_s"]:.1f} s；工作站 本地 CPU，无 Colab/超算，Colab 消耗 0 CU。','']
    (a.out/'results_v3.md').write_text('\n'.join(lines))
    print('DONE',json.dumps({k:v['decision'] for k,v in data.items()}),'runtime_s',out['runtime_s'],flush=True)
if __name__=='__main__':main()
