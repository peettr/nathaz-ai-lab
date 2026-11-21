#!/usr/bin/env python3
"""Single-realization Silsoe v7: causal inflow -> simultaneous windward Cp.
Run with a Python 3.10 environment with numpy/scipy/matplotlib/torch:
 PYTHONPATH=/usr/lib/python3/dist-packages <venv>/bin/python run.py --input <copied-CSV-dir> --out <new-output-dir>
Never writes to the source CSV directory. Output files in --out must not preexist.
"""
import argparse, csv, json, time
from pathlib import Path
import numpy as np
from scipy.signal import welch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import torch
from torch import nn

TAPS=[f'V{i}' for i in range(2,7)]+[f'H{i}' for i in range(1,7)]
PREFIX=[f'R_y{y}_z{z}' for z in (1,3,6,12) for y in (-12,-6,0,6,12)]
FS=50

def read_csv(path, columns):
    with path.open() as f: hdr=next(csv.reader(f))
    missing=set(columns)-set(hdr)
    if missing: raise ValueError(f'missing {missing}: {path}')
    d=np.loadtxt(path,delimiter=',',skiprows=1,usecols=[hdr.index(c) for c in columns],dtype=np.float64,ndmin=2)
    if not np.isfinite(d).all(): raise ValueError(f'nonfinite: {path}')
    return d

def load(root):
    pc=['step','t_s']+[f'{p}_{c}' for p in PREFIX for c in ('ux','uy','uz')]+['REF_rho','REF_ux','REF_uy','REF_uz','R_y0_z6_rho']
    tc=['step','t_s']+TAPS
    taps=np.concatenate([read_csv(root/f'S600v7_seg{s}_taps.csv',tc) for s in (1,2)])
    probes=np.concatenate([read_csv(root/f'S600v7_seg{s}_probes.csv',pc) for s in (1,2)])
    if len(taps)!=32100 or not np.array_equal(taps[:,0],probes[:,0]) or np.any(np.diff(taps[:,0])!=16):
        raise ValueError('step seam/cadence/count mismatch')
    if not np.allclose(taps[:,1],taps[:,0]*.00125,atol=1e-4): raise ValueError('time mismatch')
    keep=taps[:,1]>=42
    t=taps[keep,1]; pr=probes[keep]; tp=taps[keep]
    assert len(t)==30001
    # Causal 2-s boxcar REF pressure; edge initialized from past at t=42, no future leakage.
    # Calculated across full original sequence before slicing to retain 40-42 s history.
    r=probes[:,pc.index('REF_rho')]
    cs=np.r_[0.,np.cumsum(r)]; idx=np.arange(len(r)); lo=np.maximum(0,idx-99)
    smooth=(cs[idx+1]-cs[lo])/(idx-lo+1)
    ref_s=smooth[keep]
    vel=pr[:,[pc.index('REF_'+c) for c in ('ux','uy','uz')]]
    x=pr[:,[pc.index(f'{p}_{c}') for p in PREFIX for c in ('ux','uy','uz')]].reshape(-1,20,3)
    # Reference q measured on training partition only (never use test denominator for model fit).
    itr=t<462; q=np.mean(.5*pr[itr,pc.index('REF_rho')]*np.sum(vel[itr]**2,axis=1))
    y=(tp[:,2:]-ref_s[:,None])/(3*q)
    u=x[:,PREFIX.index('R_y0_z6'),2]; U=u[itr].mean()
    return t,x,y,u,U,q

class TCN(nn.Module):
    def __init__(self):
        super().__init__()
        layers=[]; inc=60
        for d in (1,2,4,8):
            layers += [nn.ConstantPad1d((4*d,0),0),nn.Conv1d(inc,32,5,dilation=d),nn.ReLU()]
            inc=32
        self.net=nn.Sequential(*layers)
        self.head=nn.Sequential(nn.Linear(32,48),nn.ReLU(),nn.Linear(48,len(TAPS)))
    def forward(self,x): return self.head(self.net(x)[:,:,-1])

def score(y,p):
    d=p-y
    rm=np.sqrt(np.mean(d*d,axis=0)); corr=[]; std=[]; peaks=[]
    for j in range(y.shape[1]):
        corr.append(float(np.corrcoef(y[:,j],p[:,j])[0,1]) if np.std(p[:,j])>1e-12 else None)
        std.append(float(np.std(p[:,j])/np.std(y[:,j])))
        peaks.append([float(p[:,j].min()-y[:,j].min()),float(p[:,j].max()-y[:,j].max())])
    return dict(rmse=rm.tolist(),correlation=corr,std_ratio=std,peak_min_max_signed_error=peaks,
                pooled_rmse=float(np.sqrt(np.mean(d*d))),mean_tap_rmse=float(np.mean(rm)),
                mean_tap_corr=float(np.mean([c for c in corr if c is not None])),
                mean_tap_std_ratio=float(np.mean(std)),
                mean_abs_peak_min_error=float(np.mean(np.abs(np.array(peaks)[:,0]))),
                mean_abs_peak_max_error=float(np.mean(np.abs(np.array(peaks)[:,1]))))

def main():
    a=argparse.ArgumentParser();a.add_argument('--input',type=Path,required=True);a.add_argument('--out',type=Path,required=True);args=a.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    for name in ['metrics.json','results.md','timeseries.png','spectrum.png']:
        if (args.out/name).exists(): raise FileExistsError(args.out/name)
    np.random.seed(13);torch.manual_seed(13);torch.set_num_threads(3)
    t,x,y,u,U,q=load(args.input)
    # 42..462 train, 462..522 validation, 522..642 independent held-out test.
    # To supply full history only, indices must have at least 64 preceding samples.
    win=64; ids=np.arange(win-1,len(t))
    tr=ids[t[ids]<462]; va=ids[(t[ids]>=462)&(t[ids]<522)]; te=ids[t[ids]>=522]
    print('samples',len(t),'train/val/test',len(tr),len(va),len(te),'U_lattice',U,'q_lattice',q,flush=True)
    # quasi-steady: Cp_mean fitted only on train, speed from center of 1h rack at z=6m.
    cpmean=y[tr].mean(axis=0); qs=cpmean[None,:]*(u[te][:,None]/U)**2
    # Strong causal linear FIR: each of 20 rack points x 3 velocity components,
    # 10 lags with 0.10 s spacing spanning 0..0.9 s, multivariate ridge fit.
    # Fixed alpha 100 on standardized features; intercept and scales train-only.
    lags=np.arange(10)*5
    def design(sel):return np.concatenate([x[sel-l] .reshape(len(sel),60) for l in lags],axis=1)
    Xtr=design(tr);Xv=design(va);Xte=design(te)
    mx=Xtr.mean(axis=0); sx=Xtr.std(axis=0);sx=np.where(sx<1e-9,1.,sx)
    A=(Xtr-mx)/sx; Ymean=y[tr].mean(axis=0)
    alpha=100.
    gram=A.T@A;gram.flat[::len(gram)+1]+=alpha
    coef=np.linalg.solve(gram,A.T@(y[tr]-Ymean))
    linear=(Xte-mx)/sx@coef+Ymean
    linear_val=(Xv-mx)/sx@coef+Ymean
    print('FIR val RMSE',float(np.sqrt(np.mean((linear_val-y[va])**2))),flush=True)
    # TCN sees 1.28 s history at 50 Hz, 20*3 channels. All moments train-only.
    xm=x[tr].reshape(-1,60).mean(axis=0); xs=x[tr].reshape(-1,60).std(axis=0);xs=np.maximum(xs,1e-8)
    ym=y[tr].mean(axis=0);ys=y[tr].std(axis=0);ys=np.maximum(ys,1e-6)
    xf=((x.reshape(-1,60)-xm)/xs).astype('float32')
    def window(sel):return torch.from_numpy(np.stack([xf[sel-k] for k in range(win-1,-1,-1)],axis=-1))
    Wtr=window(tr);Wva=window(va);Wte=window(te)
    Ztr=torch.from_numpy(((y[tr]-ym)/ys).astype('float32'))
    model=TCN();optim=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01)
    best=1e9; best_state=None;best_ep=None;patience=0
    for ep in range(1,37):
        model.train(); order=torch.randperm(len(tr))
        for batch in order.split(384):
            pred=model(Wtr[batch]);loss=((pred-Ztr[batch])**2).mean()
            optim.zero_grad();loss.backward();optim.step()
        model.eval()
        with torch.no_grad():
            zv=np.concatenate([model(w).numpy() for w in Wva.split(512)])
        val=float(np.sqrt(np.mean((zv*ys+ym-y[va])**2)))
        print('TCN epoch',ep,'val_rmse',val,flush=True)
        if val<best-1e-5:
            best=val;best_ep=ep;best_state={k:v.detach().clone() for k,v in model.state_dict().items()};patience=0
        else:patience+=1
        if patience>=6:break
    model.load_state_dict(best_state);model.eval()
    with torch.no_grad(): zp=np.concatenate([model(w).numpy() for w in Wte.split(512)])
    neural=zp*ys+ym
    forecasts={'quasi_steady':qs,'linear_FIR':linear,'TCN':neural}
    metrics={k:score(y[te],v) for k,v in forecasts.items()}
    wins=int(np.sum(np.array(metrics['TCN']['rmse'])<np.array(metrics['linear_FIR']['rmse'])))
    gain=1-metrics['TCN']['mean_tap_rmse']/metrics['linear_FIR']['mean_tap_rmse']
    summary=dict(source='Silsoe LBM v7 single realization',window_s=[42,642],split_s=dict(train=[42,462],validation=[462,522],test=[522,642]),samples=dict(train=len(tr),validation=len(va),test=len(te)),taps=TAPS,
                 rack=PREFIX,reference=dict(U_lattice=float(U),q_lattice=float(q),Cp='(rho_tap - causal 2s smooth rho_REF)/(3*q_train)',U='R_y0_z6_uz'),
                 FIR=dict(lags_samples=lags.tolist(),ridge_alpha=alpha),TCN=dict(best_epoch=best_ep,val_rmse=best),
                 model_wins_against_FIR=wins,model_rmse_improvement_fraction=float(gain),metrics=metrics)
    (args.out/'metrics.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    # Comparable PSD on full held-out 120 s; only 0.1-5 Hz visualized.
    j=TAPS.index('V2');i=np.arange(0,min(len(te),1000))
    fig,ax=plt.subplots(figsize=(12,4.5));ax.plot(t[te[i]],y[te[i],j],label='LBM target',lw=.8)
    for k,p in forecasts.items():ax.plot(t[te[i]],p[i,j],label=k,lw=.9,alpha=.85)
    ax.set(xlabel='physical time (s)',ylabel='Cp',title='V2 windward, first 20 s of held-out test');ax.legend();fig.tight_layout();fig.savefig(args.out/'timeseries.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5));f,ps=welch(y[te,j],fs=FS,nperseg=2048)
    ax.semilogy(f,ps,label='LBM target',lw=1.8)
    for k,p in forecasts.items():
        _,ps=welch(p[:,j],fs=FS,nperseg=2048);ax.semilogy(f,ps,label=k)
    ax.set(xlim=(.1,5),xlabel='Hz',ylabel='Cp²/Hz',title='V2 test PSD, Welch 2048 / 50% overlap');ax.legend();ax.grid(alpha=.3)
    fig.tight_layout();fig.savefig(args.out/'spectrum.png',dpi=150);plt.close(fig)
    lines=['# Silsoe v7 入流—迎风 Cp 时程最小试验','',
      '同一单次 LBM-LES 入流实现、正迎风、11 个迎风测点；这里“实测时程”仅指 LBM 目标时程，**不是现场测压验证**。',
      '数据：`21_Digital_Wind_Tunnel/04_Outputs/silsoe600_v7/raw_600s/`，只读；引用其 `analyze.py:87-103` 的测点、动压口径。',
      f'样本 {len(t)}，42–642 s，50 Hz；训练 42–462 s、验证 462–522 s、检验 522–642 s，严格顺序；起始 1.26 s 只作历史窗口。',
      f'Cp=(ρ_tap−ρ_REF的因果2 s滑动均值)/(3q)，q=训练段 REF 点的平均 0.5ρ|u|²={q:.7g} 格子单位；准定常 U_ref=入口后 1h 排架中心 R_y0_z6 的训练均值 uz={U:.7g} 格子速度。',
      '准定常 Cp_mean 仅训练段拟合。线性传递函数：20点×3分量，0–0.9 s 的 0.1 s 间隔十个因果滞后，固定岭惩罚 100；TCN 1.28 s 输入，四层因果膨胀卷积，验证段选择最优 epoch。归一化与选择从不使用检验段。',
      '持续性 Cp(t+Δ)=Cp(t) 只适于提前 Δ 预测；本试验是同步 t 的入流→压力映射，故不列该基线。','',
      '| 方法 | 迎风11点等权 RMSE Cp | 相关系数均值 | 脉动标准差比均值 | 最小Cp绝对误差均值 | 最大Cp绝对误差均值 |',
      '|---|---:|---:|---:|---:|---:|']
    for k,m in metrics.items():lines.append(f"| {k} | {m['mean_tap_rmse']:.4f} | {m['mean_tap_corr']:.3f} | {m['mean_tap_std_ratio']:.3f} | {m['mean_abs_peak_min_error']:.3f} | {m['mean_abs_peak_max_error']:.3f} |")
    lines.extend(['','按预定判据：TCN 相对线性 FIR 的逐测点 RMSE 等权均值改善 '+f'{gain:.1%}，改善测点 {wins}/11；'+('达到明显好过。' if gain>=.2 and wins>=8 else '未达到“明显好过”。'),
       '每点 RMSE、相关、标准差比、检验段极值有符号误差见 `metrics.json`；时程 `timeseries.png` 与 Welch 0.1–5 Hz `spectrum.png`。',
       '注意：风压只在迎风平均 Cp 对实验有条件验证，脉动和极值只作为模拟输出诊断；本试验不能外推至别的建筑、风向或来流。',
       '文献评价口径：`16_PETW/05_Literature_Wiki/wiki/liang2_shared_library/sources/NF6S3H9N.md`，PDF pp.1–3：该文采用 LES 高频数值结果为代理参照，并非实验真值；其几何和任务与本试验不同。',
       '数据限制：`21_Digital_Wind_Tunnel/04_Decisions/LBMPV_v7_Acceptance_Verdict_20261013.md:9–19`；参考伪振荡和2 s平滑：`21_Digital_Wind_Tunnel/04_Decisions/LBMPV_Diag_r1_Verdict_20261013.md:11–24,39–40`。',
       '本试验数值与判断：无文献依据，基于本线数据。',''])
    (args.out/'results.md').write_text('\n'.join(lines))
    print('RESULT',json.dumps({'gain':gain,'wins':wins,'rmse':{k:v['mean_tap_rmse'] for k,v in metrics.items()},'epoch':best_ep}),flush=True)

if __name__=='__main__':main()
