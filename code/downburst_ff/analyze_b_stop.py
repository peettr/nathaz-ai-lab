"""Reduce the completed A3-B stop matrix; never alter prior artifacts."""
import json,tarfile,io,math
from pathlib import Path
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
H=Path(__file__).resolve().parent
src=H/'B_stop_small_1015.tar.gz'
old=json.loads((H/'prior_26_stop_1015.json').read_text())['metrics']
with tarfile.open(src) as tar:
 files={m.name:tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
new=[json.loads(v) for k,v in files.items() if k.endswith('.json') and k not in ('manifest.json','completion.json','parity_ok.json') and not k.endswith('_parity.json')]
manifest=json.loads(files['manifest.json'])
assert json.loads(files['completion.json'])=={'old_successes':26,'new_successes':70,'expected':96,'failed':[]}
assert len(new)==70 and len(old)==26 and len(manifest)==96
assert all(x['returncode']==0 for x in new)
keys=lambda r:(r['case'],r['seed'],r['group'])
oldkeys={keys(x) for x in old};newkeys={keys(x) for x in new};expected={keys(x) for x in manifest}
assert len(oldkeys)==26 and len(newkeys)==70 and not oldkeys&newkeys and oldkeys|newkeys==expected
rows=old+new;lookup={keys(x):x for x in rows}
ca=['I_near','III_offset'];ss=[112,203,317,419,523,631]
groups=['G0_50s','G1_instant','G2_real_1D','G3_real_2D','G4_T5','G4_T10','G4_T20','G4_T40']
fields=['tower_resultant_max_kNm','tower_top_yaw_absmax_kNm','blade1_root_flapwise_negative_magnitude_kNm','tower_fore_aft_positive_max_kNm','tower_fore_aft_negative_magnitude_kNm','blade1_root_flapwise_positive_max_kNm','rotor_speed_overshoot_vs_12p1_pct']
summary={};ratios={};gates={}
for c in ca:
 summary[c]={};ratios[c]={}
 for g in groups:
  rr=[lookup[(c,s,g)] for s in ss];assert len(rr)==6
  summary[c][g]=dict(metrics_median={m:float(np.median([r['metrics'][m] for r in rr])) for m in fields},metrics_by_seed={str(r['seed']):r['metrics'] for r in rr},lead_by_seed={str(r['seed']):r.get('actual_lead_s') for r in rr})
  if g not in ('G0_50s','G1_instant'):
   summary[c][g]['reduction_vs_G1_by_seed_pct']={m:{str(s):(float(100*(lookup[(c,s,'G1_instant')]['metrics'][m]-lookup[(c,s,g)]['metrics'][m])/lookup[(c,s,'G1_instant')]['metrics'][m]) if lookup[(c,s,'G1_instant')]['metrics'][m]>0 else None) for s in ss} for m in fields}
   summary[c][g]['median_paired_reduction_pct']={m:float(np.median([v for v in summary[c][g]['reduction_vs_G1_by_seed_pct'][m].values() if v is not None])) if any(v is not None for v in summary[c][g]['reduction_vs_G1_by_seed_pct'][m].values()) else None for m in fields}
   summary[c][g]['reduction_of_medians_pct']={m:float(100*(1-summary[c][g]['metrics_median'][m]/summary[c]['G1_instant']['metrics_median'][m])) if summary[c]['G1_instant']['metrics_median'][m]>0 else None for m in fields}
 for m in fields:
  ratios[c][m]={}
  for rg in ('G2_real_1D','G3_real_2D'):
   byseed={}
   for s in ss:
    baseline=lookup[(c,s,'G1_instant')]['metrics'][m];real=lookup[(c,s,rg)]['metrics'][m];ideal=lookup[(c,s,'G4_T5')]['metrics'][m];den=baseline-ideal
    byseed[str(s)]=(float((baseline-real)/den) if baseline>0 and den>=.01*baseline else None)
   valid=[v for v in byseed.values() if v is not None]
   # Ratio of paired benefits, not a ratio of group-median levels.
   ratios[c][m][rg]=dict(per_seed=byseed,median_valid=float(np.median(valid)) if valid else None,n_valid=len(valid))
 yaw=summary[c]['G2_real_1D']['median_paired_reduction_pct']['tower_top_yaw_absmax_kNm']
 blade=summary[c]['G2_real_1D']['median_paired_reduction_pct']['blade1_root_flapwise_negative_magnitude_kNm']
 tower=summary[c]['G2_real_1D']['median_paired_reduction_pct']['tower_resultant_max_kNm']
 gates[c]=dict(yaw_reduction_median_paired_pct=yaw,blade_negative_reduction_median_paired_pct=blade,tower_reduction_median_paired_pct=tower,passes=bool((yaw>=10 or blade>=10) and tower>=-5),definition='median of six paired percent reductions; tower increase limit <=5%')
parity=json.loads(files['parity_ok.json'])
out=dict(scope='A3-B stop groups only, full 2x6x8',expected=96,old_v4_success=26,new_colab_success=70,completed=96,parity=parity,
    source='26 local segment_b_v4 metrics_B_partial_20261014 + 70 Colab a3_b_stop_1015',
    event='first rotor-disk 3s mean >13 m/s to last >25 m/s plus 60s',
    trigger='G0 50s continuous rotor-disk exceedance, G1 instant rotor-disk 3s mean, G2/G3 upstream x-plane 3s detection, G4 rotor crossing minus T; offline replay via ServoDyn SD_Time',
    fields=fields,groups=groups,seeds=ss,rows=rows,summary=summary,benefit_ratio_vs_G4_T5=ratios,gates=gates)
path=H/'metrics_B_stop.json'
encoded=json.dumps(out,indent=2,ensure_ascii=False)+'\n'
if path.exists():assert path.read_text()==encoded
else:path.write_text(encoded)
plt.rcParams['font.size']=9
metric_keys=fields[:3]
fig,axs=plt.subplots(2,3,figsize=(16,8))
for i,c in enumerate(ca):
 for j,m in enumerate(metric_keys):
  ax=axs[i,j]
  for k,g in enumerate(groups):
   vals=[lookup[(c,s,g)]['metrics'][m] for s in ss]
   ax.scatter(np.full(6,k)+np.linspace(-.13,.13,6),vals,s=13,c='gray',alpha=.65)
   ax.scatter([k],[np.median(vals)],marker='_',s=370,c='tab:red',linewidth=2.5)
  ax.set_xticks(range(8),['G0','G1','G2','G3','T5','T10','T20','T40'],rotation=35)
  ax.set_title(c+ (' (yaw rate limited)' if i else ''))
  ax.set_ylabel(m+' [kN m]');ax.grid(alpha=.25)
fig.suptitle('A3-B stop groups: six seeds (gray), median (red) | Nguyen 2012 analytic + Kaimal/Veers approximate turbulence; OpenFAST 5.0, ROSCO 2.10.6')
fig.tight_layout();f=H/'median_scatter_B_stop.png'
if not f.exists():fig.savefig(f,dpi=150)
plt.close(fig)
fig,axs=plt.subplots(1,4,figsize=(16,4))
c='III_offset'
for g,color in [('G1_instant','black'),('G2_real_1D','tab:orange'),('G4_T5','tab:blue')]:
 k=f'{c}_s112_{g}.npz'
 assert k in files,k
 d=np.load(io.BytesIO(files[k]));t=d['Time'];
 series=(np.hypot(d['Wind1VelX'],d['Wind1VelY']),d['BldPitch1'],np.hypot(d['TwrBsMxt'],d['TwrBsMyt']),d['YawBrMzp'])
 for ax,y in zip(axs,series):ax.plot(t,y,label=g,lw=.75,color=color)
for ax,title in zip(axs,['hub horizontal wind [m/s]','blade pitch [deg]','tower resultant [kN m]','tower-top yaw [kN m]']):
 ax.set(title=title,xlabel='simulation time [s]');ax.grid(alpha=.2)
axs[0].legend(fontsize=7)
fig.suptitle('III_offset seed 112 under 0.3 deg/s yaw limit | Nguyen 2012 analytic + Kaimal/Veers approximation; OpenFAST 5.0 / ROSCO 2.10.6')
fig.tight_layout();f=H/'typical_seed_B_stop.png';assert not f.exists();fig.savefig(f,dpi=150);plt.close(fig)
lines=['# A3 分段 B：湍流下击暴流预视提前停机（G0–G4）','',
 '完成 96/96：工作站 v4 的 26 个成功算例保留，Colab 补 70 个，不跑 G5–G8。此前 26 个的各自 provenance 均记载在风盒开头补 14 帧（7 s）的 v4 时间修正；Colab 同法再生，并用 I_near/112/G1 复算塔底合成峰，差 0.000%。',
 '所有仿真用同一 OpenFAST 5.0.0 + ROSCO 2.10.6 改版控制库（Apache-2.0），变桨前馈增益 0，TYCOn=0，偏航限速 0.3°/s；Case III 的偏航落后是限速下的物理响应，载荷照报。',
 '以下判据用六个同种子的配对降幅取中位数；同时保留各组绝对指标的六种子中位数，避免把不同统计量混用。事件窗口是转子盘 3 s 平均风速首次 >13 m/s 至最后 >25 m/s 后 60 s。',
 '', '## 结果与预定判据','']
for c in ca:
 gate=gates[c]
 lines.append('### '+c+('（偏航限速下）' if c=='III_offset' else ''))
 lines.append('|组|塔底合成峰中位 (kN·m)|塔顶偏航矩峰中位 (kN·m)|叶根面外负峰幅值中位 (kN·m)|G1配对降幅中位（塔/偏航/叶负，%）|')
 lines.append('|---|---:|---:|---:|---:|')
 for g in groups:
  z=summary[c][g];mm=z['metrics_median'];red=z.get('median_paired_reduction_pct',{})
  vals=' / '.join(f'{red[x]:.2f}' if red.get(x) is not None else '—' for x in metric_keys)
  lines.append(f"|{g}|{mm[metric_keys[0]]:.2f}|{mm[metric_keys[1]]:.2f}|{mm[metric_keys[2]]:.2f}|{vals}|")
 lines.append(f"判据：G2 相对 G1 的配对中位降幅，偏航 {gate['yaw_reduction_median_paired_pct']:.2f}%、叶负 {gate['blade_negative_reduction_median_paired_pct']:.2f}%、塔底 {gate['tower_reduction_median_paired_pct']:.2f}%。结果："+('预视提前停机有稳健收益（仅本入流/控制律）' if gate['passes'] else '湍流下收益不稳健（仅本入流/控制律）')+'。')
 lines.append('G2/G3 对 G4_T5 的收益比例逐种子及有效值中位见 JSON：分母非正或不足 G1 的 1% 置 null，不外推缺值。')
 lines.append('')
lines += ['## 方法与参数来源','',
 '|参数|取值与来源|','|---|---|',
 '|解析风暴与路径|Nguyen (2012) §3、Table 4.4（PDF p.66–67、114）|',
 '|湍流幅值、谱|ε=0.1、u′=ε κ Um：Nguyen (2012) PDF p.71 Eq.3.12；Kaimal/Veers PDF p.72–75；此处有限点、频率离散为近似|',
 '|x相干/网格|exp(−3 f Δx/12 m/s) 与相位平移；y/z 衰减10；转子7×7、预视3×3；均为假设|',
 '|预视和阈值|上游1D/2D 独立抽样，1 s 低通 + 1 s 延迟；3 s 均值 >25 m/s：任务指定/假设；G0 连续 50 s 规则参照 Nguyen PDF p.112–113|',
 '|触发方式|所有触发先从风场离线确定、再以 SD_Time 重放；不是在线传感器闭环控制验证|',
 '|偏航与控制|偏航限速0.3°/s、TYCOn=0、前馈增益0：任务指定；ROSCO 2.10.6 改版 Apache-2.0|',
 '', 'BTS 转子平面在 OpenFAST 中仍以文件平均风速作局部平移；上游信号是独立的解析+部分相干 4D 场，不是从 BTS 单平面复制。G2/G3 用上游信号越限时刻实际触发；局部测得 L/U 只记在 metadata，不用转子真值替代。',
 '逐种子各项载荷、转速超调、G3/G4 各档、相对 G1 的配对降幅与收益比例见 metrics_B_stop.json。图分别为 median_scatter_B_stop.png 与 typical_seed_B_stop.png（标题注明数据来源）。',
 'Colab 会话 ideas-a3-bstop-1015：完成后停止，sessions 不含本会话。运行前账号余额 1332.78 CU、终止后 1321.55 CU，期间其他会话并发，账号变化不能归于本试验。会话增量费率约 6.77 CU/h、运行约 28 min；本会话约 3–4 CU（估算，非单会话账单），低于 100 CU。仅下载压缩指标/时程与日志摘要，原大输出留在已停止的 Colab 临时环境。工作站 未运行 OpenFAST，HOLD 标志未动。',
 '']
f=H/'RESULTS_B_stop.md';assert not f.exists();f.write_text('\n'.join(lines))
print(json.dumps({'count':len(rows),'parity':parity,'gates':gates,'files':[str(path),str(f)]},ensure_ascii=False))
