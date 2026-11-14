#!/usr/bin/env python3
"""Report only verified v2 results, never overwrite existing files."""
from pathlib import Path
import json,numpy as np
root=Path(__file__).resolve().parent
p=json.loads((root/'v2/metrics.json').read_text());h=[0,.5,1,2,3,5,8]
def f(x):return '—' if x is None else f'{x:.3f}'
def half(vals):
    threshold=vals[0]/2
    for i in range(1,len(vals)):
        if vals[i]<=threshold:
            return f'{h[i-1]+(h[i]-h[i-1])*(threshold-vals[i-1])/(vals[i]-vals[i-1]):.2f}'
    return '>8'
rows=[]
for s,d in sorted(p['distances_m'].items(),key=lambda q:q[1]):
    for label in ('raw','acoustic_notch'):
        seq=[p['preview'][label][s][str(x)] for x in h]
        rows.append(f'| {s} | {d:g} | {label} | '+ ' | '.join(f(v['corr']) for v in seq)+f' | {half([v["corr"] for v in seq])} |')
pr=p['preview']['raw']['P_x-10.00'];cases=[]
for k,case in p['control'].items():
    b=case['feedback']
    cases.append(f'| {k} | feedback | — | '+ ' | '.join(f(b[q]) for q in ('x_rms','x_peak','acc_rms','acc_peak','stroke_peak','control_rms','hit_fraction'))+' | — |')
    for s in sorted(p['distances_m_m'] if 'distances_m_m' in p else p['distances_m'],key=lambda q:p['distances_m'][q]):
        for t in h:
            v=case[s][str(t)];gain=100*(1-v['acc_rms']/b['acc_rms'])
            cases.append(f'| {k} | {s} | {t:g} | '+ ' | '.join(f(v[q]) for q in ('x_rms','x_peak','acc_rms','acc_peak','stroke_peak','control_rms','hit_fraction'))+f' | {gain:+.2f}% |')
    v=case['perfect_8s'];gain=100*(1-v['acc_rms']/b['acc_rms'])
    cases.append(f'| {k} | truth-8s | 8 | '+ ' | '.join(f(v[q]) for q in ('x_rms','x_peak','acc_rms','acc_peak','stroke_peak','control_rms','hit_fraction'))+f' | {gain:+.2f}% |')
valid=[]
for k,c in p['control'].items():
    b=c['feedback']
    for s in p['distances_m']:
        for t in h:
            v=c[s][str(t)];gain=1-v['acc_rms']/b['acc_rms']
            if gain>=.1 and v['stroke_peak']<=b['stroke_peak']+1e-12:valid.append((k,s,t,gain))
raw_halves={s:half([p['preview']['raw'][s][str(x)]['corr'] for x in h]) for s in p['distances_m']}
notch_halves={s:half([p['preview']['acoustic_notch'][s][str(x)]['corr'] for x in h]) for s in p['distances_m']}
lines=['# A2：近场预视与行程受限 AMD 最小试验','','预先固定判据：预视前馈相对同一纯反馈，结构加速度 RMS 降低 ≥10% 且阻尼器行程峰值不增大，才算“有用”；结果不更改此闸门。','','## 数据、时序与边界',f"单次 Silsoe v7 LBM 仿真数据（非实测）；42–642 s，50 Hz。train 48–462 s、validation 462–522 s、测试发报 522–634 s，τ≤8 s 的测试目标仍在 642 s 以前。每个站点 z=1/3/6 m × 三分量速度；P_x−33.05 固定入口剔除；排架 R_y0 独立一站。FIR 用当前及过去 0–6 s（0.1 s 间隔）、训练 PCA 最多九维；岭惩罚 100/1000/10000 仅验证集选。训练与验证按 10 Hz，测试 50 Hz。原 CSV 只读且哈希与 `../lbm_transfer/provenance.json` 一致，拷贝到 WSL scratch；不跨 seg1/seg2 拼接点。",'',f"Cp=(ρtap−过去/当前 100 帧因果 2 s REF ρ 均值)/(3q)，q=训练窗平均 ½ρ_REF|u_REF|²={p['q_train_lattice']:.9g} 格子单位；整窗恒定分母（不是逐时 REF q）。压力不作预测输入，仅速度。附带的 acoustic_notch 目标经 0.27/0.52/0.95 Hz，Q=20 的离线双向陷波；仅作诊断，非在线滤波，边界附近可能有微小前视泄漏。两个口径的 τ 曲线与半相关时间均列出。v7 同一入流的空场建筑处完整 q 尚无现成同窗时程，本次不能计算该副口径，不能把别的入流 v8 空场替代。参见 `21_Digital_Wind_Tunnel/04_Decisions/LBMPV_REF_q_Drift_20261014.md:45`。","","## 相关—提前量—站点（主算恒定训练 REF q；滤波设置见第三列）",'| 速度站点 | 面距 m | Cp 目标 | r τ0 | r .5 | r 1 | r 2 | r 3 | r 5 | r 8 | r 减半 τ s |','|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|']+rows
lines+=['',f"半相关 τ（相对于各站 τ0）：原始 {raw_halves}；陷波 {notch_halves}。未达到的记 >8。判断不能从相关单独推得控制增益；见 `v2/preview.png`。",'',"测试误差和技巧分数（两种基线）均逐 τ/站保存在 `v2/metrics.json` 的 preview/raw 与 preview/acoustic_notch 中；下表摘近场站以检查持续性基线：",'| τ s | r | RMSE Cp | 均值基线 RMSE | 均值技巧 1−RMSE/基线 | 持续性 RMSE | 持续性技巧 |','|---:|---:|---:|---:|---:|---:|---:|']
for h0 in h:
    v=pr[str(h0)];lines.append(f'| {h0:g} | {f(v["corr"])} | {f(v["rmse"])} | {f(v["mean_baseline_rmse"])} | {f(v["skill_mean"])} | {f(v["persistence_rmse"])} | {f(v["skill_persistence"])} |')
lines+=['',"RMSE 为 11 点各自 RMSE 后等权平均；r 为 11 点 Pearson 相关等权平均；持续性在 τ>0 用测试时刻 Cp(t) 预测 Cp(t+τ)，此基线属离线可用的当前压力对照而非本试验允许的速度输入。","","## 控制模型与全组合指标",f"立方体 6×6 m 迎风面代理：V2–V6 高度剖面与 H1–H6 横向剖面采用 Voronoi 代表宽度，C(y,z)=V(z)+H(y)−V(3.01 m) 的可分离加性插值；V(3.01) 在 V3/V4 间线性插值。11 个系数及站点坐标在 `v2/metrics.json`、原始 `21_Digital_Wind_Tunnel/desktop_repo/fluidx3d/inflow/taps.csv`。F=Σ(w_i Cp_i) 为平均迎风面 Cp 的无量纲代理（相当于 ∫Cp dA/36 m²），移除训练期均值；不是全建筑力，不把格子密度/速度硬换成实楼物理力。面积插值系数可能为负（校正交叉点），不是逐点实测面积。",'',f"质量 M=1、AMD m=.05、阻尼比 .02，频率近谱峰 {p['frequencies_Hz']['near_spectral_peak']:.4f} Hz 与远共振 {p['frequencies_Hz']['off_resonance']:.4f} Hz；行程限 ±.12/±.025（无量纲位移），u_max=2·测试风力标准差（这是力标度的假设，给所有方案相同）。0.1 s ZOH 质量-弹簧-阻尼器 + 相对行程 r；同一状态 LQR 反馈，Q=diag(ω²,1,20ω²,.2)，R=.08（另见 params.md）。前馈为由离散 LQR 的闭环 Bellman 方程给出的已知扰动卷积，取每次发报的 0..τ 预测，预测各离散 τ 独立训练后在间隔内线性插值；τ=0 有同时刻预测。纯反馈前馈置零；truth-8s 使用同控制律的真实未来力，属于“完美信号对照”，固定控制律与饱和/硬止挡下并非最优控制上界。力饱和，触限后位置裁剪、相对外冲速度非弹性归零并把冲量转移给主体，冲量计入离散加速度；是简化止挡，不代表实物细节。","",'| 频率/行程 | 方案/站点 | τ s | x RMS | x 峰值 | a RMS | a 峰值 | 行程峰值 | u RMS | 触限比例 | a RMS 降幅 |','|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']+cases
lines+=['',f"固定闸门满足的组合数：{len(valid)}；组合明细：{valid if valid else '无'}。固定控制律的真实 8 s 预视对照也未达 10%（见表）；模型在此标度与参数下没有证明实用加速度收益。图：`v2/control.png`。",'',"## 限制与一句话判定","本试验的预视提前量由同一段单次 LBM 实现给出，陷波结果与原始口径相近，但测试时段和声学滤波法未作独立实现/无泄漏审计；不等于现场可部署预报。较远站可能 τ>0 比 τ=0 略好，反映平流时滞而非无条件距离增益。小样本、假设控制参数、代理面荷载、简化硬止挡、不含风向/多种事件；不能推广到实体建筑。科学判断无文献依据，基于本线数据；文献仅用于几何坐标见任务书引用源，不称仿真为实测。","","判定：近场速度对迎风 Cp 的统计预视为秒级，但在本次行程受限 AMD 假设下未过预定 10% 加速度与不增行程的联合闸门；作为进一步受控基准试验的线索，当前不支持转为工程增益结论。",'',f"本地 工作站 CPU 运行，0 Colab CU、无超算；耗时 {p['runtime_s']:.1f} s。根目录 metrics.json/图为先行诊断版本，不作为交付结果；所有正式数字只用 `v2/metrics.json` 与 `v2/*.png`。",'']
(root/'results.md').write_text('\n'.join(lines))
params=['# A2 参数来源与假设','','| 参数 | 取值 | 来源/性质 | 依据和检验范围 |','|---|---|---|---|',f"| 时间步、切分与 Cp | 0.02 s, 42–642 s；q={p['q_train_lattice']:.9g} | 本线 `../lbm_transfer/run_v4b.py:27,44–53,68–99` | 保留原协议；测试发报 <634 s，提前 ≤8 s |",'| 探针与面距 | −30/−25/−20/−15/−10 m，排架 −27.1 m；迎风面 −3 m | 本线 `../lbm_transfer/run_v4b.py:18–26` | −33.05 固定边界剔除，x≥−5、z12 剔除 |','| Cp REF 压力与动压 | 因果 100 帧 REF ρ；训练窗恒定 q | 本线 `../lbm_transfer/run_v4b.py:45–53` | 16.8 Hz 压力振荡，以因果 2 s 压力平滑；空场同窗 q 缺失，不伪造 |','| 声学模态滤波 | 0.27/.52/.95 Hz，iirnotch Q20 双向 | 频率来自任务书；Q20 与离线方法为假设 | 原始/陷波目标两组敏感性；双向滤波仅离线诊断 |','| 面压力面积权重 | C(y,z)=V(z)+H(y)−V(3.01)，Voronoi 代表宽度；36 m² 归一 | 坐标来自 `21_Digital_Wind_Tunnel/desktop_repo/fluidx3d/inflow/taps.csv:1–23`；插值是假设 | 不把 11 点当成完整二维压力场；仅迎风面代理 |','| 质量与尺度 | M=1, m=.05；F=ΣwCp 减训练均值 | 假设 | 无实楼尺度；m/M=.05，未单独扫描，结论仅限本假设 |',f"| 频率 | {p['frequencies_Hz']['near_spectral_peak']:.5f} / {p['frequencies_Hz']['off_resonance']:.3f} Hz | 谱峰根据训练荷载 Welch (`run_a2.py`)，远共振选择是假设 | 近/远两档敏感性；前者低于声学带，仅用于代理 |",'| 结构阻尼比 | .02 | 假设 | 为轻阻尼原型；未扫描，不是实楼取值 |','| 行程限制 | ±.12 / ±.025 | 假设 | 宽松/紧两档敏感性；无量纲位移 |','| LQR 权重与饱和 | Q=diag(ω²,1,20ω²,.2), R=.08；u_max=2σ_F | 假设 | 固定同一反馈/前馈/完美信号对照；不是经验证的物理执行器 |','| 止挡 | 位置裁剪、向外相对速度非弹性归零、主体接收动量 | 假设 | 冲量计入加速度；真实止挡材料和接触时长未建模 |','| 控制离散步长 | .1 s | 假设，沿用输入历史间距 | 在 50 Hz Cp 上每五帧控一次；未扫离散步长 |','','无文献依据的质量、刚度、限位、控制器、力尺度全部明确为假设；上述频率与行程两档是任务要求的最低敏感性，不能声称性能稳健。']
(root/'params.md').write_text('\n'.join(params)+'\n')
print('written',len(rows),'preview rows',len(cases),'control rows','valid',len(valid),'halves',raw_halves,notch_halves)
