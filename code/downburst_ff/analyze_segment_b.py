#!/usr/bin/env python3
"""Reduce completed A3-B OpenFAST cases without altering run roots or previous results."""
import json, math
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path('./lab_a3/downburst_ff/segment_b_v4')
HERE=Path(__file__).resolve().parent
FIELDS=['Time','Wind1VelX','Wind1VelY','Wind1VelZ','BldPitch1','RotSpeed','RootMyb1','YawBrMzp','TwrBsMxt','TwrBsMyt','NacYaw']
METRICS=['tower_resultant_max_kNm','tower_fore_aft_positive_max_kNm','tower_fore_aft_negative_magnitude_kNm',
         'tower_top_yaw_absmax_kNm','blade1_root_flapwise_positive_max_kNm','blade1_root_flapwise_negative_magnitude_kNm',
         'rotor_speed_overshoot_vs_12p1_pct']
GROUPS=['G0_50s','G1_instant','G2_real_1D','G3_real_2D']+[f'G4_T{T}' for T in (5,10,20,40)]
CASES=['I_near','III_offset'];SEEDS=[112,203,317,419,523,631]

def read_out(path,cols=FIELDS):
    with path.open() as fh:
        for i,line in enumerate(fh):
            if i==6: names=line.split();break
    data=np.loadtxt(path,skiprows=8,usecols=[names.index(n) for n in cols],ndmin=2)
    return dict(zip(cols,data.T))

def measures(d,p,start):
    t=d['Time'];event_start=p['rotor_3s_first13_abs_s']-start
    event_end=p['rotor_3s_last25_abs_s']+60-start
    event=(t>=event_start)&(t<=event_end)
    x=d['TwrBsMxt'][event];y=d['TwrBsMyt'][event];m=d['RootMyb1'][event]
    return dict(tower_resultant_max_kNm=float(np.hypot(x,y).max()),
        tower_fore_aft_positive_max_kNm=float(y.max()),
        tower_fore_aft_negative_magnitude_kNm=float(max(0.,-y.min())),
        tower_top_yaw_absmax_kNm=float(np.abs(d['YawBrMzp'][event]).max()),
        blade1_root_flapwise_positive_max_kNm=float(m.max()),
        blade1_root_flapwise_negative_magnitude_kNm=float(max(0.,-m.min())),
        rotor_speed_overshoot_vs_12p1_pct=float(100*(d['RotSpeed'][event].max()/12.1-1)))

def main():
    target=HERE/'metrics_B_partial_20261014.json';report=HERE/'RESULTS_B_partial_20261014.md'
    plots=[HERE/'median_scatter_B_partial.png',HERE/'typical_seed_B_partial.png']
    if any(p.exists() for p in [target,report]+plots):raise RuntimeError('refuse overwrite B artifacts')
    manifest=json.loads((ROOT/'manifest.json').read_text());ledger=[json.loads(s) for s in (ROOT/'ledger.jsonl').read_text().splitlines()]
    assert len(manifest)==len(CASES)*len(SEEDS)*len(GROUPS)
    successes=[r for r in ledger if r['returncode']==0]
    assert len(successes)==len({(r['case'],r['seed'],r['group']) for r in successes})
    rows=[];lookup={};example={}
    for r in ledger:
        if r['returncode']!=0:continue
        f=Path(r['runroot'])/'NREL-5MW.out'; d=read_out(f)
        assert abs(d['Time'][-1]-(r['end_abs_s']-r['start_abs_s']))<.051,(f,d['Time'][-1])
        p=json.loads((ROOT/f"{r['case']}_s{r['seed']}"/'provenance.json').read_text())
        m=measures(d,p,r['start_abs_s'])
        row=dict(case=r['case'],seed=r['seed'],group=r['group'],trigger_abs_s=r['trigger_abs_s'],
          actual_lead_s=r['actual_lead_s'],event_window_abs_s=[p['rotor_3s_first13_abs_s'],p['rotor_3s_last25_abs_s']+60],
          metrics=m,runroot=r['runroot'],wall_s=r['wall_s'])
        rows.append(row);lookup[(r['case'],r['seed'],r['group'])]=row
        if r['seed']==112 and r['group'] in ('G1_instant','G2_real_1D','G4_T5'):
            example[(r['case'],r['group'])]=d
    summaries={};ratios=[];gates={}
    for case in CASES:
        summaries[case]={}
        for group in GROUPS:
            sample=[lookup[(case,seed,group)] for seed in SEEDS if (case,seed,group) in lookup]
            summaries[case][group]=dict(n=len(sample),metrics_median={k:float(np.median([z['metrics'][k] for z in sample])) for k in METRICS} if sample else {},
               metrics_values={k:[z['metrics'][k] for z in sample] for k in METRICS},actual_lead_s=[z['actual_lead_s'] for z in sample])
        for metric in METRICS:
            for group in ['G2_real_1D','G3_real_2D']+[f'G4_T{T}' for T in (5,10,20,40)]:
                pairs=[(lookup[(case,seed,'G1_instant')]['metrics'][metric],lookup[(case,seed,group)]['metrics'][metric])
                    for seed in SEEDS if (case,seed,'G1_instant') in lookup and (case,seed,group) in lookup]
                reductions=[100*(b-q)/b for b,q in pairs if b>0]
                summaries[case][group].setdefault('relative_G1',{})[metric]=dict(n_pairs=len(pairs),
                   per_seed_pct=reductions,median_per_seed_pct=float(np.median(reductions)) if reductions else None,
                   reduction_of_medians_pct=float(100*(1-np.median([q for b,q in pairs])/np.median([b for b,q in pairs]))) if pairs and np.median([b for b,q in pairs])>0 else None)
            for T in (5,10,20,40):
                perfect=f'G4_T{T}';pp=[]
                for seed in SEEDS:
                    keys=[(case,seed,g) for g in ('G1_instant','G2_real_1D',perfect)]
                    if all(k in lookup for k in keys):
                        b,q,p=[lookup[k]['metrics'][metric] for k in keys]
                        den=b-p;status='ok' if b>0 and den>=.01*b else 'not_applicable_perfect_benefit_under_1pct_or_nonpositive'
                        pp.append(dict(seed=seed,ratio=(b-q)/den if status=='ok' else None,status=status,baseline=b,real=q,perfect=p))
                valid=[x['ratio'] for x in pp if x['ratio'] is not None]
                ratios.append(dict(case=case,metric=metric,perfect_T_s=T,per_seed=pp,
                   median_valid_ratio=float(np.median(valid)) if valid else None,n_valid=len(valid)))
        if all(summaries[case][g]['n']==6 for g in ('G1_instant','G2_real_1D')):
            yaw=summaries[case]['G2_real_1D']['relative_G1']['tower_top_yaw_absmax_kNm']['median_per_seed_pct']
            blade=summaries[case]['G2_real_1D']['relative_G1']['blade1_root_flapwise_negative_magnitude_kNm']['median_per_seed_pct']
            tower=summaries[case]['G2_real_1D']['relative_G1']['tower_resultant_max_kNm']['median_per_seed_pct']
            gates[case]=dict(yaw_reduction_median_pct=yaw,blade_negative_reduction_median_pct=blade,
               tower_reduction_median_pct=tower,passes=bool((yaw>=10 or blade>=10) and tower>=-5))
        else:gates[case]=dict(passes=None,reason='fewer than six matched seeds')
    missing=[r for r in manifest if (r['case'],r['seed'],r['group']) not in lookup]
    output=dict(scope='A3-B turbulent event; OpenFAST BTS 7x7; all trigger times frozen from input before response',
         root=str(ROOT),expected=len(manifest),completed=len(rows),missing=[(r['case'],r['seed'],r['group']) for r in missing],
         errors=[z for z in ledger if z['returncode']!=0],solver_wall_s=float(sum(z['wall_s'] for z in ledger)),
         threshold='causal trailing 3s mean horizontal rotor disk vector >25m/s; upstream uses independent 3x3 x-plane, 1s LPF+1s delay',
         event='first 3s mean rotor speed >13m/s through last 3s mean rotor speed >25m/s plus 60s',
         metrics=rows,summary=summaries,gates=gates,benefit_ratios=ratios)
    target.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
    # paired scatter: six raw-seed measurements and medians, all group variants
    keys=['tower_resultant_max_kNm','tower_top_yaw_absmax_kNm','blade1_root_flapwise_negative_magnitude_kNm']
    fig,axs=plt.subplots(2,3,figsize=(17,9))
    for row,case in enumerate(CASES):
        for col,key in enumerate(keys):
            ax=axs[row,col]
            for gi,g in enumerate(GROUPS):
                vals=[lookup[(case,s,g)]['metrics'][key] for s in SEEDS if (case,s,g) in lookup]
                if not vals:continue
                ax.scatter(np.full(len(vals),gi)+np.linspace(-.08,.08,len(vals)),vals,s=16,c='tab:gray',alpha=.55)
                ax.scatter(gi,np.median(vals),marker='_',s=350,c='tab:red',linewidth=2)
            ax.set_xticks(range(len(GROUPS)),['G0','G1','G2','G3','T5','T10','T20','T40'],rotation=30)
            ax.set_ylabel(key+' [kN m]');ax.set_title(case);ax.grid(alpha=.2)
    fig.suptitle('Six seeds: points; red bars: medians | Source: Nguyen 2012 analytic + Kaimal/Veers (assumed x coherence), OpenFAST 5.0 / ROSCO 2.10.6')
    fig.tight_layout();fig.savefig(plots[0],dpi=140);plt.close(fig)
    fig,axs=plt.subplots(2,4,figsize=(16,8))
    for ri,case in enumerate(CASES):
        p=json.loads((ROOT/f'{case}_s112'/'provenance.json').read_text())
        for group,color in [('G1_instant','k'),('G2_real_1D','tab:orange'),('G4_T5','tab:blue')]:
            d=example.get((case,group))
            if d is None:continue
            xx=d['Time']+p['start_abs_s'];spd=np.hypot(d['Wind1VelX'],d['Wind1VelY'])
            for ax,v in zip(axs[ri],(spd,d['BldPitch1'],np.hypot(d['TwrBsMxt'],d['TwrBsMyt']),d['YawBrMzp'])):
                ax.plot(xx,v,label=group,color=color,lw=.8)
        for j,label in enumerate(('hub horizontal wind [m/s]','pitch [deg]','tower resultant [kN m]','top yaw [kN m]')):
            axs[ri,j].set(xlabel='time after touchdown [s]',ylabel=label,title=case);axs[ri,j].grid(alpha=.2)
    axs[0,0].legend(fontsize=8);fig.suptitle('Seed 112 | Data: Nguyen 2012 analytic + Kaimal/Veers approximation; OpenFAST 5.0 / ROSCO 2.10.6')
    fig.tight_layout();fig.savefig(plots[1],dpi=140);plt.close(fig)
    lines=['# A3 分段 B：暂停时的部分记录，不是六种子验收','',f'完成 {len(rows)}/{len(manifest)}，累计 OpenFAST 有账本求解 {output["solver_wall_s"]:.1f} 秒；另有无账本中断，不计入本值。原 A/A2 文件未改写。',
      '23:00 后 Lead 因 C 盘余量低于 40 GB 已暂停；本执行方未及时看到暂停记录，又尝试恢复一次（未完成新算例）。现已停止，不得按本表判定预设六种子闸门。',
      '六种子、两条路径，转子 7×7 TurbSim BTS 全场；上游 1D/2D 独立 3×3。所有 G 组用同一 ROSCO 2.10.6 (Apache-2.0) 控制库且变桨前馈增益 0。',
      '触发是先按输入风速离线确定时刻、再以 SD_Time 重放；不是经在线传感器闭环验证的产品控制器。事件窗口为转子 3s 均值首次 >13 m/s 至最后 >25 m/s 后 60s。',
      '湍流采用 Nguyen (2012) PDF p.71 Eq 3.12 的 ε=0.1 幅值调制，以及 p.72–75 §3.4 的 Kaimal 谱/Veers 频域、Cholesky 相干；这里有限点/频率离散属于近似，非原论文完全复现。',
      '纵向相干 exp(−3 f Δx/12 m/s) 并带平流相位；侧向/竖向衰减系数各10，参考风速12 m/s、网格7×7、上游3×3、预视1s低通+1s延迟均标为假设。下击暴流解析形函数与两路径取 Nguyen PDF p.66–67 / Table 4.4 PDF p.114，现场剪切0.2见 PDF p.78–79。',
      '3s 滑动平均 >25 m/s 为任务指定假设（借 IEC 3s 阵风口径，不代表 IEC 停机规范）； G0 等50s，G1 当刻，G2/3 各自上游信号一越限就触发；G4 依转子事件提前 T。局部实测风速计算 L/U 仅记录作预计到达，不利用转子真值替上游；现实可执行时刻为上游越限，可能较预计到达还早。',
      '数值方法局限：BTS 场在 OpenFAST 内仍以文件平均速度作局部平移；但预视测量取独立 x 平面的解析+部分相干随机 4D 场，并未从转子单平面冻流盒复制。停机时间在场生成后离线重放。',
      '', '## 中位数与预设判据','']
    for case in CASES:
        lines.append(f'路径 {case}: '+('预视提前停机有稳健收益' if gates[case]['passes'] else '湍流下收益不稳健' if gates[case]['passes'] is False else '未判定（缺六种子）'))
        lines.append('|组|塔底合成峰 (kN·m)|塔顶偏航峰 (kN·m)|叶根面外负峰幅值 (kN·m)|相对 G1：偏航/叶负/塔底中位降幅 %|')
        lines.append('|---|---:|---:|---:|---:|')
        for g in GROUPS:
            su=summaries[case][g];m=su['metrics_median'];rel=su.get('relative_G1',{})
            if not m:continue
            def reduce(k):return f"{rel[k]['median_per_seed_pct']:.2f}" if k in rel and rel[k]['median_per_seed_pct'] is not None else '—'
            lines.append(f"|{g} (n={su['n']})|{m['tower_resultant_max_kNm']:.1f}|{m['tower_top_yaw_absmax_kNm']:.1f}|{m['blade1_root_flapwise_negative_magnitude_kNm']:.1f}|{reduce('tower_top_yaw_absmax_kNm')} / {reduce('blade1_root_flapwise_negative_magnitude_kNm')} / {reduce('tower_resultant_max_kNm')}|")
        lines.append('')
    lines += ['完整七项指标每种子的值及中位数、各 G4 档和 G3 的 G1 配对降幅、收益比例均见 metrics_B.json；收益比逐种子只在完美 T5 收益 ≥G1 的1%且正值时有效，否则为 null。',
      '参数来源表：ε=0.1 Nguyen 2012 PDF p.71 Eq.3.12；Kaimal/Veers/相干 PDF p.72–75 Eqs.3.13–3.20；风暴案例 Table 4.4 PDF p.114；50s 保护 PDF p.112–113；NREL 5MW 模型见本地 ff_smoke_feedback；其余 7×7、3×3、x衰减3、yz衰减10、12m/s参考、1s过滤和1s延迟均假设。',
      '软件：OpenFAST 5.0.0、ROSCO 2.10.6（两者 Apache-2.0）；NumPy 2.4.6 (BSD-3-Clause)、SciPy 1.17.1 (BSD-3-Clause)、Matplotlib 3.11.2 (PSF-2.0)。',
      '图 median_scatter_B.png 与 typical_seed_B.png 数据来源均标明 Nguyen 2012 解析场 + Kaimal/Veers 近似 + OpenFAST/ROSCO。',
      '']
    report.write_text('\n'.join(lines))
    print('B ANALYZED',len(rows),'/',len(manifest),'gates',gates)
if __name__=='__main__':main()
