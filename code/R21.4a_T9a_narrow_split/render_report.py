#!/usr/bin/env python3.10
"""Render verified read-only T9a tables into a compact handoff."""
import hashlib,json
from pathlib import Path
O=Path(__file__).resolve().parent
r=json.loads((O/'T9a_result.json').read_text());p=json.loads((O/'narrow16.json').read_text());o=json.loads((O/'offsets.json').read_text());n=json.loads((O/'near6.json').read_text())
assert len(p)==16 and len(n)==12 and len(o)==16
f=lambda x:f'{x:.6f}'
lines=['# R21.4a T9a 只读拆分诊断','', '定义：r_G=Σ(Su/Uref)/Σobs，Δr=r_0.5−r_1，Uref=3.9286416。组别与判据逐字口径见 04_Decisions/R21.4a_T9_窄街近墙偏慢_拆分诊断_设计与判据_20261117.md:16–33。T2c 主配准、离墙 2 m；本报告不运行求解器。','', '## 冻结分组与判词','', '|组|N|r_1m|r_0.5m|Δr|','|---|---:|---:|---:|---:|']
for name,g in r['groups'].items():lines.append(f"|{name}|{g['count']}|{f(g['r_1m'])}|{f(g['r_0p5m'])}|{f(g['delta_r'])}|")
lines +=['',f"N_close 对 N 增量的贡献={f(r['N_close_contribution'])}；R_seed={f(r['R_seed'])}，3R_seed={f(3*r['R_seed'])}。N_far Δr={f(r['groups']['N_far']['delta_r'])}≥0.10 且≥3R_seed，判词：{r['verdict']}。这里只说与 1 m 窄街欠分辨相容，不作因果归因。",'', '种子逐档 r_N（全部为 1 m 关闭态；T2d_s101/T5_s101 和 T2d_s102/T5_s102 各为同一输出的再取值，不当独立六种子）：']
for s,v in r['seed_r_N'].items():lines.append(f'- {s}: {f(v)}')
lines +=['', '## 16 个窄街点','', '|id|wall_m|width_min_m|obs|1m Su/Uref|0.5m Su/Uref|1m fluid_corners/solid_weight|0.5m fluid_corners/solid_weight|最近固体节点格数¹|','|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for q in p:lines.append(f"|{q['id']}|{f(q['wall_m'])}|{f(q['width_min_m'])}|{f(q['obs'])}|{f(q['Su_over_Uref_1m'])}|{f(q['Su_over_Uref_0p5m'])}|{q['fluid_corners_1m']}/{f(q['solid_weight_1m'])}|{q['fluid_corners_0p5m']}/{f(q['solid_weight_0p5m'])}|{f(q['nearest_solid_1m_T5_s102']['distance_cells'])}|")
lines +=['','¹ 最近固体节点格数来自 T5 s102 off 的 1 m thin 原生 fluid 掩膜，仅取 2 m 测点的两层垂直插值节点及其周围 40 格内最近三维节点；并非 T2c B2u 的原生几何表面距离。其余逐点列取 T2c 原始记录。','', '## fluid_corners<8 剔除后另报（不改判词）','',f"剔除 ID {r['filtered_report_only']['excluded_ids']}。",'','|组|N|r_1m|r_0.5m|Δr|','|---|---:|---:|---:|---:|']
for name,g in r['filtered_report_only']['groups'].items():lines.append(f"|{name}|{g['count']}|{f(g['r_1m'])}|{f(g['r_0p5m'])}|{f(g['delta_r'])}|")
lines +=['',f"剔除版贴面贡献={f(r['filtered_report_only']['N_close_contribution'])}；原判词仍是“{r['verdict']}”。",'', '## 近墙 6 点三档','', '1 m 关／1 m T5 开按相同种子配对；0.5 m 是 T2c 单个固定样本，并非对应种子的配对结果。','', '|种子|ID|obs|1m关|T5开|0.5m|','|---:|---:|---:|---:|---:|---:|']
for q in n:lines.append(f"|{q['seed']}|{q['id']}|{f(q['obs'])}|{f(q['one_m_off'])}|{f(q['one_m_T5_on'])}|{f(q['half_m_T2c_primary'])}|")
lines +=['', '## T5 s102 关水平配准 ±0.5 m','', 'x/y 各自单轴偏移；同一 T5 thin，三线性插值（包括固体节点），不是重新计算壁距/重跑。数值均为 Su/Uref。','', '|ID|中心|x−0.5|x+0.5|y−0.5|y+0.5|最大绝对差|','|---:|---:|---:|---:|---:|---:|---:|']
for q in o:
 vals=[q[k]['Su_over_Uref'] for k in ('x-0.5m','x+0.5m','y-0.5m','y+0.5m')];center=q['center']['Su_over_Uref'];lines.append('|'+ '|'.join([str(q['id']),f(center),*[f(x) for x in vals],f(max(abs(x-center) for x in vals))])+'|')
lines +=['','点 50/74 在这四个小偏移下仍接近零；不能凭该偏移诊断把 0.5 m 与 1 m 差全部归为配准。','', '## 溯源','', '种子逐点输入及哈希（T2d 四个候选文件含逐点数据；T2d_s101 与 T5_s101、T2d_s102 与 T5_s102 的 r 重合）：','']
for x in r['seed_files']:lines.append(f"- {x['label']}: {x['path']}；sha256 {x['sha256']}")
for key,digest in r['source_sha256'].items():lines.append(f'- {key} sha256 {digest}')
script=O/'analyze_t9a.py';lines +=[f"- 计算脚本 {script}；sha256 {hashlib.sha256(script.read_bytes()).hexdigest()}",'', '数据表：T9a_result.json、narrow16.json、near6.json、offsets.json 均在本目录；只读旧根，未上 GPU/TACC。']
(O/'RESULT_REPORT_20261117.md').write_text('\n'.join(lines)+'\n')
print('report',O/'RESULT_REPORT_20261117.md','lines',len(lines),'script_sha256',hashlib.sha256(script.read_bytes()).hexdigest())
