#!/usr/bin/env python3
"""Build a sourced T03 completion report from CRC metrics JSON."""
import json,sys
from pathlib import Path
p=Path(sys.argv[1]); o=Path(sys.argv[2]); d=json.loads(p.read_text())
lines=['# L22.6-02 T03 v1.1 B0/B1 结果（10-21，美东）','','数据源：CFD 线 E7 输入 / TInF 上游提交 8737a0d5；CRC 求解 1600473、统计 1600525。原版 DFM 的 B1 只额外提供 psi 文件，但原 BC 不读取。使用冻结 TASK_SPEC_T03_v1.md v1.1。','','## 执行与复核','','ComputeOps CO-19e9635e；CRC 求解运行根 `/groups/kareem/[用户]/L22_6/L22_6_T03_v11_20261021_03`、后处理运行根 `/groups/kareem/[用户]/L22_6/L22_6_T03_analysis_20261021_01`。预检与提交分开，均只提交一次；`rc-job` 分别登记 1600473、1600525。两作业退出码均为 0。求解日志六阶段退出码均为 0；B0/B1 探针各 80052 行，原始 0.0005 s、分析抽样 0.005 s，统计窗 5–40 s，入口五个高度各 10 个 y 探针。实验卡见 `EXPERIMENT_CARD_03.md` 与 `EXPERIMENT_CARD_analysis.md`（对应 CRC 运行根亦有同内容）。','','早期 _01 的 1600405 在环境加载阶段失败；_02 的 1600419 因 shell 全局 tag 覆盖导致 B1 路径必错，在确认队列状态后撤销。两旧根均保留；这些不是科学结果。详见两张历史实验卡。','','## 零扭转 B0：输入目标偏差','','偏差定义为 (测得−目标)/|目标|；目标为零时不报相对差。R 与 L 的全分量逐高度表见 `template/B0_target_deviation_full.csv`，原始统计见 `metrics_B0_B1.json`。下表只列代表性分量（百分数），删除的尺度记作「右删失」。','','| z (m) | U 偏差 | Rxx 偏差 | Lx,u 偏差 | Ly,u 偏差 |','|---:|---:|---:|---:|---:|']
for z,t in d['target'].items():
 b=d['B0']['heights'][z]; u=(b['mean_global_mps'][0]/t['U']-1)*100; r=(b['R_local']['xx']/t['R']['xx']-1)*100
 lx=b['Lx_local']['x']['value_m']; ly=b['Ly_local']['x']['value_m']; x=f'{(lx/t["L_matrix"][0][0]-1)*100:+.1f}%' if lx is not None else '右删失'; y=f'{(ly/t["L_matrix"][1][0]-1)*100:+.1f}%' if ly is not None else '右删失'
 lines.append(f'| {z} | {u:+.1f}% | {r:+.1f}% | {x} | {y} |')
lines += ['','## 空白 B1：只改输入、原版忽略 psi','','各指标定义：方向误差 = wrap(atan2(平均 Uy,平均 Ux)−psi) 的绝对值；R 在局部坐标旋转后逐分量相对 B0 为 (B1−B0)/|B0|；x′ 尺度是单点时间自相关首次零交点前梯形积分×|U|，y′ 用面内 y 相距 d=s/cosψ、时差 τ=s tanψ/|U| 的相关（τ 线性插值），相对差同式。右删失时差值为 null。完整五高度六个 R 分量、x′/y′ 各三分量和删失标记在 `metrics_B0_B1.json` 的 `B1_vs_B0`。','','| z (m) | 目标 psi | 实测方向 | |Δψ| | Rxx 相对 B0 | Lx,u 相对 B0 | Ly,u 相对 B0 |','|---:|---:|---:|---:|---:|---:|---:|']
for z,v in d['B1_vs_B0'].items():
 h=d['B1']['heights'][z]; rr=v['R_relative_delta']['xx']*100; l=v['scale_relative_delta']; x=l['Lx_local']['x']['relative_delta']; y=l['Ly_local']['x']['relative_delta']
 sx=f'{x*100:+.1f}%' if x is not None else '右删失'; sy=f'{y*100:+.1f}%' if y is not None else '右删失'
 lines.append(f'| {z} | {h["target_psi_deg"]:.2f}° | {h["mean_direction_deg"]:+.2f}° | {v["direction_abs_error_deg"]:.2f}° | {rr:+.1f}% | {sx} | {sy} |')
lines += ['','非对角 Rxy/Ryz 的 B0 基线接近零，以其直接作分母会出现很大的病态相对比值（完整 JSON 保留原定义数字），不能把它们单独理解为物理误差大小；`B0_target_deviation_full.csv` 标明零分母/近零项。B0/B1 的 Ly,z(z=0.9 m) 和 Ly,u(z=1.5 m) 未在有限探针范围出现零交点，按预定规则右删失，不填有限尺度。','','## 打分台状态','','`grade_T03.py` + `analyze_T03.py` 已编写并通过语法检查；静态预检仅查类名/psi 标记，候选 BC 的编译和 CFD 求解在 CRC 计算节点执行，失败写 L0；通过后使用相同统计计算局部指标 JSON。原版目录缺 Veer 三源码的 L0 静态分支已在 CRC 实测（`grade_L0_smoke.json`，不是 B1 统计得分）。尚无被测候选 Veer BC，因此编译—求解—打分的成功分支未端到端验证，不能声称打分台全面合格。候选新作业须单独预检、ComputeOps 覆盖、唯一运行根与实验卡，不可在 工作站 运行。可选私有参考实现未做。','','结论限于本算例与上述指标：原版忽略 psi 的 B1 平均方向保持约 0°，方向误差随目标 psi 增大；B0 有可用的有限统计，同时部分 y′ 尺度右删失。尚未证明候选 BC 的评分成功路径可用，不应对外宣布完整打分台验收通过。']
o.parent.mkdir(parents=True,exist_ok=True); o.write_text('\n'.join(lines)+'\n'); print(o)
