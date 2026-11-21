# 生成 GATES_TABLE_v2.md：判据行取自 result.json；入口行取自 inlet_same_height_multiy.json；高度诊断取自 ../../T2b_heightmatch/heightmatch.json
import json
r=json.load(open('result.json'));I=json.load(open('inlet_same_height_multiy.json'));H=json.load(open('../../T2b_heightmatch/heightmatch.json'))
P,C=r['tables']['primary_05_05_0'],r['tables']['control_1_1_0']
o=['# T2b 冻结判据表 v2（make_gates_table.py 生成；作业 3693675）\n','定义：r_i=(Su_i/Uref)/obs_i，Uref=3.9286416（两网格同一常数）；Δr_G=mean_G(r_0.5−r_1)；D_G=Δr_G−Δr_≥15；组总比=Σ_G(Su/Uref)/Σ_G obs。判据见 DESIGN_T2.md:17（10-23）；主配准 (+0.5,+0.5,0) 为 11-05 开跑前增补，对照 (+1,+1,0) 为原设计映射。\n','| 判据 | 主 (+0.5,+0.5,0) | 对照 (+1,+1,0) |','|---|---|---|']
f=lambda x:f'{x:+.6f}'
rows=[('ΔMAE ≤0.005',lambda t:f(t['delta_mae']),'delta_mae_le_005'),('<4 m D ≥0.10',lambda t:f(t['groups']['<4']['D']),'narrow_D_ge_010'),('<4 m 改善 ≥3/4',lambda t:f"{t['groups']['<4']['improved']}/4",'narrow_improved_ge_3_of_4'),('≥15 m |Δr| ≤0.05',lambda t:f(t['groups']['>=15']['delta_r']),'wide_abs_delta_r_le_005'),('六近墙改善 ≥4/6',lambda t:f"{t['near_group']['improved']}/6",'near_improved_ge_4_of_6'),('六近墙 Δr − 宽组 Δr ≥0.10',lambda t:f(t['near_group']['delta_r']-t['groups']['>=15']['delta_r']),'near_delta_r_excess_ge_010')]
for n,g,k in rows:o.append(f"| {n} | {g(P)} {'过' if P['gates'][k] else '不过'} | {g(C)} {'过' if C['gates'][k] else '不过'} |")
o.append(f"| 全部同过 | {P['all_gates_pass']} | {C['all_gates_pass']} |\n")
for nm,t in (('主',P),('对照',C)):
    w=t['groups']['>=15'];o.append(f"{nm}：≥15 m 组总比 {w['ratio_total_1']:.3f}→{w['ratio_total_05']:.3f}，组 MAE {w['MAE_1']:.4f}→{w['MAE_05']:.4f}，改善 {w['improved']}/{w['N']}；80 点组总比 {t['total']['ratio_total_1']:.3f}→{t['total']['ratio_total_05']:.3f}；六近墙组总比 {t['near_group']['ratio_total_1']:.3f}→{t['near_group']['ratio_total_05']:.3f}\n")
bad=[p['id'] for p in C['near_points'] if p['fluid_corners']==0];o.append(f"对照配准下近墙点 {bad} 的 8 角全在固体内（Su_05=0），对照近墙两项不作物理证据。\n")
o.append('入口诊断（不是测点）：比值=mean_y‖⟨u⟩‖_0.5 / mean_y‖⟨u⟩‖_1，x=2 m，y=7 处；‖⟨u⟩‖ 是时均矢量的模，不是测点用的 ⟨|u|⟩；1 m 网格在 1.5 m 高为两节点插值、0.5 m 为节点，口径不同：'+'；'.join(f"{w['h_m']} m {w['U_ratio']:.3f}" for w in I['rows'])+'\n')
o.append('采样高度诊断（VTK 标签比实际高 1 个 dx；两网格在标签 2.0 取样时离墙约 1.5 m 对 1.75 m）：')
for k,v in H.items():o.append(f"- {k}：宽组 Δr {v['wide_dr']:+.4f}，全过={v['all']}")
open('GATES_TABLE_v2.md','w').write('\n'.join(o)+'\n')
