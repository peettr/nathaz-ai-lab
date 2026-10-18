#!/usr/bin/env python3
"""Four-point height ablation, reproducing run_v4b protocol without overwrites.
Usage: python run_v4c.py --input <local CSV copies> --out <lab folder>
"""
import argparse, json, time
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import torch
from run import read_csv
import run_v4b as base

GROUPS = {key: [f'{key}_z{z}' for z in (1,3,6,12)] for key in ('R_y0','P_x-10.00','P_x-15.00','P_x-20.00')}
FILES = ('results_v4c.md','metrics_v4c.json','distance_v4c.png')

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    for name in FILES:
        if (a.out/name).exists(): raise FileExistsError(a.out/name)
    torch.set_num_threads(3);np.random.seed(13);torch.manual_seed(13)
    start=time.monotonic()
    t,xa,xb,y,q=base.load(a.input)
    existing=base.RACK+base.B1
    xx=np.concatenate([xa,xb],axis=1).reshape(-1,len(existing),3)
    extra=[s for stations in GROUPS.values() for s in stations if s not in existing]
    cols=['step','t_s']+[f'{s}_{c}' for s in extra for c in ('ux','uy','uz')]
    rows=np.concatenate([read_csv(a.input/f'S600v7_seg{i}_probes.csv',cols) for i in (1,2)])
    if len(rows)!=32100 or not np.all(np.diff(rows[:,0])==16):raise ValueError('extra probe cadence/count')
    keep=rows[:,1]>=42
    if not np.allclose(rows[keep,1],t,atol=1e-5):raise ValueError('extra probe time alignment')
    added=rows[keep,2:].reshape(len(t),len(extra),3)
    all_names=existing+extra
    xyz=np.concatenate((xx,added),axis=1)
    old=json.loads((a.out/'metrics_v4b.json').read_text())
    families={}
    for key,stations in GROUPS.items():
        x=xyz[:,[all_names.index(s) for s in stations],:].reshape(len(t),12)
        test,pred,info=base.fit_family(key+'_z12',x,y,t,stations)
        met={name:base.score(y[test],val) for name,val in pred.items()}
        fir=met['linear_FIR'];cnn=met['CNN']
        families[key]={'distance_to_face_m':base.DISTANCE[key],'setup':info,'metrics':met,
                       'decision':{'CNN_gain_vs_FIR':1-cnn['mean_tap_rmse']/fir['mean_tap_rmse'],
                                   'CNN_tap_wins':int(np.sum(np.array(cnn['rmse'])<np.array(fir['rmse'])))}}
        print('FINISHED',key,'FIR RMSE',fir['mean_tap_rmse'],'CNN RMSE',cnn['mean_tap_rmse'],flush=True)
    result={'source':'Silsoe LBM-LES v7, one realization; targets are simulation, not field measurements',
            'sampling_Hz':50,'split_s':{'train':[42,462],'validation':[462,522],'test':[522,642]},
            'history_lags_s':(base.LAGS/base.FS).tolist(),'Cp_definition':'(tap rho - causal 2 s smoothed REF rho)/(3*q_train)',
            'q_train':q,'runtime_s':time.monotonic()-start,'families':families,
            'comparison':'metrics_v4b.json, same fixed seed independently trained three-height groups'}
    (a.out/FILES[1]).write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    keys=sorted(GROUPS,key=lambda k:base.DISTANCE[k]);dist=[base.DISTANCE[k] for k in keys]
    fig,axs=plt.subplots(3,1,figsize=(10,11),sharex=True,layout='constrained')
    for ax,field,label in zip(axs,('mean_tap_corr','mean_tap_rmse','mean_tap_std_ratio'),('Mean correlation (11 taps)','Mean RMSE (Cp)','Mean fluctuation std ratio')):
        for method,color in (('quasi_steady','tab:gray'),('linear_FIR','tab:blue'),('CNN','tab:orange')):
            for z12,style,mark in ((False,'--','o'),(True,'-','s')):
                fam=families if z12 else old['families']
                ax.plot(dist,[fam[k]['metrics'][method][field] for k in keys],color=color,linestyle=style,marker=mark,label=f'{method} '+('z1/3/6/12' if z12 else 'z1/3/6'))
        ax.grid(alpha=.3);ax.set_ylabel(label)
    axs[0].legend(ncol=2,fontsize=8)
    axs[-1].set_xticks(dist,[f'{d:.1f}\n{k}' for d,k in zip(dist,keys)]);axs[-1].set_xlabel('Distance to windward face (m)')
    fig.savefig(a.out/FILES[2],dpi=160);plt.close(fig)
    lines=['# Silsoe v7：单站加入 z12 的配对检验','',
        '目标为单次 LBM-LES 立方体表面模拟风压时程，并非现场实测时程；只比较该风向与入流实现。旧 v4b 文件未改动。',
        '完全沿用 `run_v4b.py` 的 Cp 口径（训练段 q，REF 密度因果过去 2 s 均值）、42–462 s 训练/462–522 s 验证/522–642 s 测试、0–6 s 每 0.1 s 历史、训练段标准化/PCA、验证选准定常时滞和 FIR 岭参数及 CNN 早停。每组 4 点各三速度分量；准定常依然只用 z3。对照三点数值直接读取此前 `metrics_v4b.json`，其 CNN 是独立重训、同随机种子，非对同一网络消融。',
        '距离定义为迎风面 x=−3 m 减探针 x；排架中心列 x=−27.1 m。排除固定边界 P_x-33.05 与 x≥−5。', '',
        '| 组/输入高度 | 距离 m | 方法 | RMSE Cp | 相关系数 | 脉动标准差比 | 加 z12 RMSE 变化 | 相关变化 | 标准差比变化 |',
        '|---|---:|---|---:|---:|---:|---:|---:|---:|']
    for k in keys:
        for method in ('quasi_steady','linear_FIR','CNN'):
            a3=old['families'][k]['metrics'][method];b4=families[k]['metrics'][method]
            fields=('mean_tap_rmse','mean_tap_corr','mean_tap_std_ratio')
            for z,values,delta in [('z1/3/6',a3,False),('z1/3/6/12',b4,True)]:
                r,c,s=(values[f] for f in fields)
                d=[b4[f]-a3[f] for f in fields]
                lines.append(f'| {k} {z} | {base.DISTANCE[k]:.1f} | {method} | {r:.4f} | {c:.3f} | {s:.3f} | '+(f'{d[0]:+.4f} | {d[1]:+.3f} | {d[2]:+.3f} |' if delta else '— | — | — |'))
    lines+=['','实际四点探针：']
    for k in keys:lines.append(f'{k}（距面 {base.DISTANCE[k]:.1f} m）：'+', '.join(GROUPS[k])+'。')
    lines+=['','判据：CNN 比同输入 FIR 的 11 点平均 RMSE 低至少 20%，且至少 8/11 点改善，才算“明显好过”。']
    for k in keys:
        d=families[k]['decision'];b=families[k]['setup'];m3=old['families'][k]['metrics']['linear_FIR'];m4=families[k]['metrics']['linear_FIR']
        lines.append(f"{k}：FIR 加 z12 后 RMSE {m4['mean_tap_rmse']-m3['mean_tap_rmse']:+.4f} Cp，相关 {m4['mean_tap_corr']-m3['mean_tap_corr']:+.3f}，脉动标准差比 {m4['mean_tap_std_ratio']-m3['mean_tap_std_ratio']:+.3f}；CNN 相对四点 FIR 改善 {d['CNN_gain_vs_FIR']:.1%}、胜 {d['CNN_tap_wins']}/11；准定常验证滞后 {b['qs_lag_s']:.1f} s、FIR 岭 {b['fir_ridge_alpha']:.0f}、CNN epoch {b['cnn_best_epoch']}。")
    lines+=['','图 `distance_v4c.png`：实线四高度，虚线原三高度；逐测点 RMSE、相关、脉动比及极值误差见 `metrics_v4c.json`，运行原始输出见 `run_v4c.log`。',
         '文献评价口径：`16_PETW/05_Literature_Wiki/wiki/liang2_shared_library/sources/NF6S3H9N.md` PDF pp.1–3；试验比较无文献依据，基于本线数据。现场核验限制：`21_Digital_Wind_Tunnel/04_Decisions/LBMPV_v7_Acceptance_Verdict_20261013.md:9–19`；REF 平滑：`21_Digital_Wind_Tunnel/04_Decisions/LBMPV_Diag_r1_Verdict_20261013.md:11–24,39–40`。',
         f'本地 工作站 CPU 耗时 {result["runtime_s"]:.1f} s；未使用 Colab/超算，Colab 消耗 0 CU。','']
    (a.out/FILES[0]).write_text('\n'.join(lines))
    print('DONE runtime_s',result['runtime_s'],flush=True)
if __name__=='__main__':main()
