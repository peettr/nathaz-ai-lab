"""Reduce Colab A3-C small metrics against immutable A3-B stop results."""
import json,statistics as st,math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
B=json.loads((P/'metrics_B_stop.json').read_text())
C=json.loads((P/'C_colab_small_20261015.json').read_text())
SEEDS=B['seeds'];CASES=['I_near','III_offset'];LOADS=B['fields'];GROUPS=['G1_instant','G2_real_1D','G3_real_2D','G1L_22','G1L_20','G1L_18']
assert len(C['storm'])==36 and len(C['stationary'])==18
assert len({(r['case'],r['seed'],r['group']) for r in C['storm']})==36
assert all(r['returncode']==0 for r in C['storm'])
old={(r['case'],r['seed'],r['group']):r for r in B['rows']}
new={(r['case'],r['seed'],r['group']):r for r in C['storm']}
assert all((case,seed,group) in old for case in CASES for seed in SEEDS for group in GROUPS[:3])
assert all((case,seed,group) in new for case in CASES for seed in SEEDS for group in GROUPS[3:])
assert len({(r['mean_mps'],r['seed']) for r in C['stationary']})==18
rules=['G1_25','G1L_22','G1L_20','G1L_18','G2_1D_25']
false={g:{'overall':sum(int(r['rules'][g]['false_stop']) for r in C['stationary']),
           'per_mean':{str(u):sum(int(r['rules'][g]['false_stop']) for r in C['stationary'] if r['mean_mps']==u) for u in (18.,20.,22.)},
           'episodes_total':sum(len(r['rules'][g]['episodes']) for r in C['stationary'])} for g in rules}
rows=list(B['rows'])+C['storm'];lookup={(r['case'],r['seed'],r['group']):r for r in rows}
def median(v):return float(st.median(v))
summary={};gate={}
for case in CASES:
 summary[case]={}
 for group in GROUPS:
  sample=[lookup[case,s,group] for s in SEEDS]
  ref=[lookup[case,s,'G1_instant'] for s in SEEDS]
  summary[case][group]={
   'median_metrics':{k:median([r['metrics'][k] for r in sample]) for k in LOADS},
   'per_seed_metrics':{str(s):lookup[case,s,group]['metrics'] for s in SEEDS},
   'median_lead_vs_G1_s':median([r['actual_lead_s'] for r in sample]),
   'per_seed_lead_s':{str(s):lookup[case,s,group]['actual_lead_s'] for s in SEEDS},
   'paired_reduction_G1_pct':{k:{'per_seed':{str(s):100*(lookup[case,s,'G1_instant']['metrics'][k]-lookup[case,s,group]['metrics'][k])/lookup[case,s,'G1_instant']['metrics'][k] for s in SEEDS},
        'median':median([100*(lookup[case,s,'G1_instant']['metrics'][k]-lookup[case,s,group]['metrics'][k])/lookup[case,s,'G1_instant']['metrics'][k] for s in SEEDS])} for k in LOADS if all(x['metrics'][k]>0 for x in ref)}
  }
 g2=summary[case]['G2_real_1D']['paired_reduction_G1_pct']['tower_top_yaw_absmax_kNm']['median']
 gate[case]={}
 for group in GROUPS[3:]:
  yaw=summary[case][group]['paired_reduction_G1_pct']['tower_top_yaw_absmax_kNm']['median']
  fgroup=false[group]['overall']/18;fpreview=false['G2_1D_25']['overall']/18
  gate[case][group]=dict(yaw_reduction_pct=yaw,G2_yaw_reduction_pct=g2,
       reaches_80pct_yaw=bool(yaw>=.8*g2),false_rate=fgroup,G2_false_rate=fpreview,
       qualifies_as_simple_substitute=bool(yaw>=.8*g2 and fgroup<=fpreview))
 gate[case]['any_simple_substitute']=any(gate[case][g]['qualifies_as_simple_substitute'] for g in GROUPS[3:])
output=dict(scope='A3-C | same B v4 storm field, ROSCO/OpenFAST; separate stationary approximation',
 expected_storm=36,completed_storm=len(C['storm']),stationary_600s=len(C['stationary']),seeds=SEEDS,
 false_stop_summary=false,storm_summary=summary,predeclared_gate=gate,
 old_B_source='metrics_B_stop.json, 96/96 including 26 provenance-limited prior cases',
 methodology='3s causal trailing mean; frozen offline triggers; false-stop defined >=1 trigger episode per 600s realization; unlatched episodes also counted',
 stationary_method=C['stationary'][0]['method'],raw_new_storm=C['storm'],raw_stationary=C['stationary'])
path=P/'metrics_C.json';assert not path.exists();path.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
# Plot two storm-path axes; same empirical false-stop x for all paths, seed scatter y.
fig,axs=plt.subplots(1,2,figsize=(14,6),sharey=True)
colors={'G1_instant':'black','G2_real_1D':'tab:blue','G1L_22':'tab:orange','G1L_20':'tab:red','G1L_18':'tab:purple'}
for ax,case in zip(axs,CASES):
 for group in colors:
  fkey={'G1_instant':'G1_25','G2_real_1D':'G2_1D_25'}.get(group,group)
  x=100*false[fkey]['overall']/18
  vals=[summary[case][group]['paired_reduction_G1_pct']['tower_top_yaw_absmax_kNm']['per_seed'][str(s)] for s in SEEDS]
  ax.scatter([x+(i-2.5)*.7 for i in range(6)],vals,color=colors[group],alpha=.45,s=18)
  ax.scatter([x],[median(vals)],color=colors[group],edgecolor='white',s=130,label=group,zorder=5)
 ax.axhline(.8*summary[case]['G2_real_1D']['paired_reduction_G1_pct']['tower_top_yaw_absmax_kNm']['median'],ls='--',lw=1,color='tab:blue')
 ax.set(title=case+(' (yaw rate-limited)' if case=='III_offset' else ''),xlabel='False stop: fraction of 18 stationary 600s trials [%]',ylabel='Top yaw-moment reduction vs G1, paired [%]')
 ax.set_xlim(-8,108);ax.grid(alpha=.25);ax.legend(fontsize=8)
fig.suptitle('Source: Nguyen 2012 + Kaimal/Veers synthetic storm, OpenFAST 5 / ROSCO 2.10.6; 6 seeds/path.\nFalse stops: stationary IEC-B sigma / Kaimal-like partial-coherence approximation, 18 trials (not certified TurbSim).')
fig.tight_layout();figpath=P/'yaw_vs_false_stop_C.png';assert not figpath.exists();fig.savefig(figpath,dpi=170);plt.close(fig)
lines=['# A3 分段 C：降阈值能否替代上游预视？','',
 '分段 B 的同一 Nguyen 2012 解析+Kaimal/Veers 部分相干下击暴流输入，新增 G1L 阈值 22/20/18 m/s：2 路径×6 种子×3 阈值=36/36 个成功 OpenFAST 5.0.0 + ROSCO 2.10.6 仿真。比较组 G1/G2/G3 使用原 B 的 96 个指标，不重跑、不覆盖。事件窗口沿用转子 3 s 平均首次 >13 m/s 至最后 >25 m/s 后 60 s。',
 '停机触发均先从输入风场离线计算，然后通过 ServoDyn SD_Time 重放；并非经过在线传感器闭环验证。所有风暴组前馈增益 0、偏航 0.3°/s、TYCOn=0；偏心 Case III 是限速下的响应。旧 B 中 26 个早期风盒仅有流程级 v4 补 14 帧的溯源，原始输出无法逐文件核验。','',
 '## 风暴中降载与提前时间','',
 '百分比按同路径同种子 G1 的偏航峰逐一配对求降幅，再取 6 种子中位数；括号为本组偏航峰绝对中位数 (kN·m)，提前时间相对转子 >25 m/s 首次时刻。塔底合成、叶根正负峰、塔底前后正负峰、转速超调均在 metrics_C.json。','']
for case in CASES:
 lines+=['路径 '+case+'：','|规则|塔顶偏航矩降幅中位 %（峰中位）|塔底合成峰中位 kN·m|提前中位 s|','|---|---:|---:|---:|']
 for g in GROUPS:
  d=summary[case][g];lines.append(f"|{g}|{d['paired_reduction_G1_pct']['tower_top_yaw_absmax_kNm']['median']:.2f} ({d['median_metrics']['tower_top_yaw_absmax_kNm']:.1f})|{d['median_metrics']['tower_resultant_max_kNm']:.1f}|{d['median_lead_vs_G1_s']:.2f}|")
 lines.append('')
lines+=['## 常规湍流误停（每个 600 s 只要触发至少一次就算一次误停）','',
 '平均风 18/20/22 m/s，各 6 个种子，共 18 个独立 600 s 输入；判定只需风速信号，无需空载 OpenFAST 求解。3 s 因果滑动均值；G2 使用与 B 同一上游 1D 3×3、1 s 滤波 + 1 s 延迟及部分相干采样。不计停机后重启；连续越限的每段次数另存 JSON。','',
 '|规则|18 m/s 触发/6|20 m/s 触发/6|22 m/s 触发/6|总误停/18|','|---|---:|---:|---:|---:|']
for g in rules:
 d=false[g];lines.append(f"|{g}|{d['per_mean']['18.0']}|{d['per_mean']['20.0']}|{d['per_mean']['22.0']}|{d['overall']}|")
lines+=['','## 预定判据','',
 '对每一路径，若某一降阈值组偏航峰配对中位降幅 ≥ G2 的 80%，且常规湍流误停率 ≤ G2，则“预视无独特价值，降阈值即可”；否则为“预视有独特价值（以更少误停换取同等降载）”。在 18 个试验的离散误停率上执行原样 ≤ 比较，未事后改阈值。','']
for case in CASES:
 d=gate[case]
 lines.append(case+': '+('预视无独特价值，降阈值即可' if d['any_simple_substitute'] else '预视有独特价值（以更少误停换取同等降载）'))
 for g in GROUPS[3:]:
  x=d[g];lines.append(f"{g}: 偏航降幅 {x['yaw_reduction_pct']:.2f}% / G2 {x['G2_yaw_reduction_pct']:.2f}%；误停 {false[g]['overall']}/18 / G2 {false['G2_1D_25']['overall']}/18；{'满足' if x['qualifies_as_simple_substitute'] else '不满足'}替代判据。")
lines+=['','## 参数来源与局限','',
 '|参数|本次取值|依据或查找/假设|','|---|---|---|',
 '|下击暴流入流、湍流|Nguyen 解析场及 ε=0.1、Kaimal/Veers|Nguyen 2012 thesis PDF p.66–75、Table 4.4 PDF p.114；同分段 B 脚本|',
 '|下击暴流种子、全场|112/203/317/419/523/631；7×7 BTS，补 14 帧|分段 B v4 同一生成脚本；14×0.5 s 修正经先前风速配准|',
 '|触发|3 s 因果滑动平均；G1L 22/20/18 m/s|Lead 本次任务指定；25 m/s、3 s 取 B 已冻结任务（3 s 为假设）|',
 '|上游现实信号|1D，3×3 空间平均；1 s 一阶滤波+1 s 延迟；纵向相干 exp(−3 f Δx/12)|B 中自定假设，不是仪器误差模型|',
 '|常规湍流强度|IEC 61400-1 Ed3 类别 B，σ1=0.14(0.75 U+5.6)|TurbSim Users Guide NREL/TP-500-46198 IEC NTM/IECKAI 参数说明；用谱形近似而非运行 TurbSim|',
 '|常规湍流谱/相干|B 的频域合成：Kaimal 形状归一化；x/y/z 衰减 3/10/10，v/u=0.8；600 s，z^0.2|脚本取 B 假设及任务指定；非完整 IEC/TurbSim 相干/方差校验。3 档×6 种子供探索，不外推误停概率|',
 '|控制|OpenFAST 5.0.0 + 改版 ROSCO 2.10.6；前馈增益 0|B 既定链；均 Apache-2.0。MATLAB/Colab GPU 未用|',
 '', '图 yaw_vs_false_stop_C.png 每点标中位、浅色为 6 种子；风暴模拟与稳态误停为不同风场样本。常规湍流非 IEC TurbSim 原版；前锋解析、离线重放、18 次短窗的误停率都限制科学外推。']
report=P/'RESULTS_C.md';assert not report.exists();report.write_text('\n'.join(lines)+'\n')
print('C_ANALYZED',len(C['storm']),len(C['stationary']),false,gate)
