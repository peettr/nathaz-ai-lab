#!/usr/bin/env python3
"""Render immutable T2 postprocessor outputs into an acceptance report."""
import csv, datetime, hashlib, json, pathlib
P=pathlib.Path(__file__).resolve().parent
R=json.loads((P/'result_complete.json').read_text())
S=json.loads((P/'selection.json').read_text())
I=json.loads((P/'inlet_same_height.json').read_text())
F=[json.loads((P/n).read_text()) for n in ('fit_05.json','fit_1.json')]
points=json.loads((P/'points_all_offsets.json').read_text())
assert len(points)==80 and {x['id'] for x in points}==set(range(1,81))
assert len(F[0])==189 and len(F[1])==56 and len(R['planes'])==8
assert R['original_max_abs_diff']==0 and all(p['gates']==R[k]['gates'] for p,k in [(R['original_table'],'original_table'),(R['iou_table'],'iou_table')])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def loc(p):return f'{p} ({p.stat().st_size} B; sha256 {sha(p)})'
def tstamp(s):return datetime.datetime.fromtimestamp(s,datetime.timezone(datetime.timedelta(hours=-5))).strftime('%m-%d %H:%M:%S EST')
with (P/'iou_all_offsets.csv').open('x',newline='') as f:
 w=csv.writer(f);w.writerow(('dx_m','z_vtk_m','offset_x_m','offset_y_m','offset_z_m','IoU','actual_zero','predicted_solid','intersection','nsegments'))
 for dx,fit in zip((.5,1),F):
  for x in fit:w.writerow((dx,x['z_vtk'],*x['offset_xyz_m'],x['iou'],x['actual_zero'],x['predicted_solid'],x['tp'],x['nsegments']))
lines=['# T2 0.5 m 只读后处理 v4 RUN','',f'资源 CO-5e5ee10d；作业 3683894，rc-job --kind post 已登记（回执见 RUN_submission.md）。Slurm COMPLETED 0:0；运行 11-05 05:44:01–05:44:57 EST，56 s；post.exitcode=0。v2 3683868 FAILED 1:0（空 IoU）；v3 3683873 FAILED 1:0（重复独占写 fit_05.json）；两旧根保留。','',f'完整产物：{loc(P/"result_complete.json")}',f'冻结结果：{loc(P/"result.json")}',f'80 点每种偏移：{loc(P/"points_all_offsets.json")}（80 ID × 27 组；含 Su、fluid_corners、solid_weight；原 +1,+1,0 与旧表最大绝对差 0）',f'配准选取：{loc(P/"selection.json")}',f'所有 IoU 数值：{loc(P/"iou_all_offsets.csv")}（0.5 m 189 行、1 m 56 行）',f'入口同高：{loc(P/"inlet_same_height.json")}',f'后处理日志：{loc(P/"post.log")}','','## 配准','STL 建筑 z 最大 59.900005 m；64 m 掩膜空，排除。按建筑实际高度 8/17/23/26/32/59 m 判 z；z=2 m 水平 IoU 选偏移，未用测点误差选。']
for dx,fit in zip((.5,1),F):
 lines += [f'{dx} m：z=2 m 的所有水平组合（z 偏移=0）：']
 for x in fit:
  if x['z_vtk']==2 and x['offset_xyz_m'][2]==0:lines.append(f"  {tuple(x['offset_xyz_m'])}: IoU {x['iou']:.9f}")
 chosen=S['chosen_05' if dx==.5 else 'chosen_1'];lines.append(f"选定水平 {chosen['horizontal_m']}，z={chosen['z_m']} m，{chosen['z_status']}；六楼顶高度 z 偏移 IoU 和：{chosen['roof_iou_sum_by_z']}，判别差 {chosen['roof_margin']:.9f}。逐高度全部偏移在 CSV。")
lines += ['','## 两套冻结判据','定义：r=模拟 Su/Uref ÷ 观测；Δr_G=mean(r_0.5−r_1)；D_G=Δr_G−Δr_≥15；ΔMAE=MAE_0.5−MAE_1。原 +1 m 冻结读法与事后补定 11-05（依据 Case A 偏移随 dx 变化）的 IoU 口径并列。']
for title,key in [('原 (+1,+1,0) m','original_table'),('IoU 选定 (+0.5,+0.5,0) m','iou_table')]:
 tab=R[key];lines+=['',title,f"80点 MAE_1={tab['total']['MAE_1']:.9f} MAE_0.5={tab['total']['MAE_05']:.9f} ΔMAE={tab['delta_mae']:+.9f}；改善/恶化/同分={tab['total']['improved']}/{tab['total']['worsened']}/{tab['total']['ties']}；总比 {tab['total']['ratio_total_1']:.6f}→{tab['total']['ratio_total_05']:.6f}",'组 | N | MAE_1→MAE_0.5 | 总比_1→总比_0.5 | Δr | D | 改善/恶化/同分']
 for g in ('<4','4-8','8-15','>=15'):
  x=tab['groups'][g];lines.append(f"{g} | {x['N']} | {x['MAE_1']:.6f}→{x['MAE_05']:.6f} | {x['ratio_total_1']:.6f}→{x['ratio_total_05']:.6f} | {x['delta_r']:+.6f} | {x['D']:+.6f} | {x['improved']}/{x['worsened']}/{x['ties']}")
 x=tab['near_group'];lines.append(f"近墙六点：MAE {x['MAE_1']:.6f}→{x['MAE_05']:.6f}，Δr={x['delta_r']:+.6f}，改善/恶化={x['improved']}/{x['worsened']}，相对宽组Δr差={x['delta_r']-tab['groups']['>=15']['delta_r']:+.6f}；宽组 |Δr|={abs(tab['groups']['>=15']['delta_r']):.6f}。")
 lines.append('点 | obs | Su_1→Su_0.5 | r_1→r_0.5 | Δr | 改善 | 流体角/固体权重')
 for p in tab['near_points']:lines.append(f"{p['id']} | {p['obs']:.6f} | {p['Su_1']:.6f}→{p['Su_05']:.6f} | {p['r_1']:.6f}→{p['r_05']:.6f} | {p['delta_r']:+.6f} | {p['improved']} | {p['fluid_corners']}/{p['solid_weight']:.6f}")
 lines.append('逐项门槛：'+json.dumps(tab['gates'],ensure_ascii=False)+'；全部同时满足='+str(tab['all_gates_pass']))
lines += ['','## 工程先决与有效性','分配网格 1000×1000×940，核心 VTK 1000×1000×540，0.5 m，原点 (0,0,-20) m；源 VTK 17,280,000,510 B。1 m 基线核心 500×500×270，2,160,000,498 B。同一 500×500×470 m 盒，顶海绵 400 格；不能把 540 输出层当分配高度。','求解器日志：62000/62000 步；末 40000 步 stride 80，日志 Avg samples=500；solver.exitcode=0，但原 T2 包装 run.exitcode=1（旧提取器索引错误），不混作求解失败。四卡 trace 与 T1c 相容性在本后处理未重新核查，工程先决不宣称全过。','入口同高 VTK 原始量：x=2,y=250 m；U=平均矢量范数，k=VTK tke（非官方目标输入核验）。高度 | U_05/U_1 (m/s) | k_05/k_1 (VTK原始) | 比值：']
for x in I['items']:
 a,b=x['pair'];lines.append(f"{x['height_m']:g} | {a['u_avg_norm_raw']:.6f}/{b['u_avg_norm_raw']:.6f} | {a['k_raw']:.6f}/{b['k_raw']:.6f} | {x['U_norm_ratio_05_over_1']:.6f}, {x['k_ratio_05_over_1']:.6f}")
lines += ['这些是运行后场值而非两个 deck 的入口边界设定一致性证明；入口同高设定 U/k 工程先决仍待 deck 逐高度/源配置核对，不能据此给网格单因素归因。','', '## 两高度平面（仅 TACC）','文件均位于 /scratch/04448/[用户]/r24_luw/T2_05m_post_v4/；float32 little endian，1000×1000；u_avg 三分量，其余单分量；时间为美东。']
for p in R['planes']:
 q=pathlib.Path(p['path']);lines.append(f"{q.name} | {p['bytes']} B | sha256 {p['sha256']} | {tstamp(p['mtime'])} | 层 {p['lower_index']}/{p['upper_index']}")
lines += ['远端 sha256sum 与 manifest 八项一致；z=1.5/2 m 原生 flags 未导出，fluid 是标量掩膜，不能冒称 flags。','', '## 结论','原口径与 IoU 口径均未同时满足 DESIGN_T2.md 预定全部条件：宽组 |Δr| 分别 0.130018 与 0.130754，均大于 0.05；原口径近墙相对宽组 Δr 差仅 0.044938，不达 0.10。按原文，宽组整体变化超过 0.05，属于“全局/入口等变化亦存在，局部归因不成立”；不称网格收敛或因果证明。IoU 口径为事后补定，不能替换原冻结判定。','','结果生成自已取回并逐字节核过 SHA 的 JSON；原有结果未移动或覆盖。']
(P/'RUN_post_v4.md').write_text('\n'.join(lines)+'\n')
print('REPORT',loc(P/'RUN_post_v4.md'),'IOU',loc(P/'iou_all_offsets.csv'))
