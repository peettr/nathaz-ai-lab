#!/usr/bin/env python3
import json, pathlib, statistics
R=pathlib.Path(__file__).resolve().parent
G=json.loads((R/'comparison_vdm_true_nearest.json').read_text())
assert len(G)==9 and sum(len(g['leg_details']) for g in G)==sum(g['qualifying_legs'] for g in G)
v=[g['relative_difference'] for g in G if g['relative_difference'] is not None]
assert len(v)==8
out=['# L26.18-02 第二轮：官方侦察 VDM 中心的 SFMR RMW 数字','',
'数据来源：NOAA/NHC 侦察存档 REPNT2 (URNT12 Vortex Data Message) 2018、2019、2022 年目录；NOAA/AOML ERDDAP `sfmr_2018_2022`；IFREMER CyclObs 11 景 SAR 结构量（第一轮结果）。',
'官方定位目录：https://www.nhc.noaa.gov/archive/recon/2018/REPNT2/ ；https://www.nhc.noaa.gov/archive/recon/2019/REPNT2/ ；https://www.nhc.noaa.gov/archive/recon/2022/REPNT2/ 。逐条原文 URL、A/B 字段见 `official_fixes.json`；各时刻 ±3 h 对应 URL 见 `comparison_vdm_true_nearest.json`。SFMR：https://erddap.aoml.noaa.gov/hdb/erddap/tabledap/sfmr_2018_2022.html 。',
'固定判据：FLAG=0、NGC≥4、SWS≥0；11 点约 10 s 风速平滑；每腿距中心最近点 ≤15 km、最远点 ≥70 km、峰半径 ≥10 km，中心时间到 SAR ±3 h；各腿峰半径中位数为 RMW_obs。同一时刻两景 SAR RMW 取中位。相对差定义 |RMW_SAR−RMW_obs|/RMW_obs。官方 A/B 字段提供实测时刻/位置，线性插值到 SFMR 逐点；不使用 b-deck/BEST/ATCF 或 SFMR 风速极小点中心。',
'穿眼腿按官方 fix 时间前后各 30 min 切入/出段；同航班 45 min 内的重复 fix 不重复计一次穿眼。每腿“中心到最近点”从整段实际航迹取极小值（不施加计算峰值时的 5 km 内界）。','',
'| 风暴 | SAR UTC | ±3 h VDM 条数 | 合格腿 | SAR RMW km | RMW_obs km | 相对差 |',
'|---|---|---:|---:|---:|---:|---:|']
for g in G:
 fmt=lambda x:f'{x:.3f}' if x is not None else '无'
 out.append(f"| {g['storm']} | {g['time_utc']} | {g['official_fixes_3h']} | {g['qualifying_legs']} | {fmt(g['rmw_sar_km'])} | {fmt(g['rmw_obs_km'])} | {fmt(g['relative_difference'])} |")
out+=['',f'合格观测时刻：{len(v)}/9；相对差中位数：{statistics.median(v):.3f}。','',
'| 风暴 | SAR UTC | 航班/腿/VDM UTC | 中心到腿最近点 km | 峰半径 km | VDM 原文 |',
'|---|---|---|---:|---:|---|']
for g in G:
 if not g['leg_details']:
  out.append(f"| {g['storm']} | {g['time_utc']} | 无合格腿 | 无 | 无 | 见 JSON 的 ±3 h 官方定位 URL |")
 for x in g['leg_details']:
  out.append(f"| {g['storm']} | {g['time_utc']} | {x['flight']} {x['leg']} {x['crossing_utc']} | {x['true_nearest_km']:.3f} | {x['peak_radius_km']:.3f} | {x['fix_url']} |")
out+=['','执行：Colab CPU 会话 `qtl-l2618-v3-vdm-1113` 11-13 16:24:51–16:36 EST 已 stop，私有/全局 sessions 均不列出。共享账户余额 1053.56→1053.54 CU，差 0.02 CU，非独占计量；按约 11 分钟 × 0.08 CU/h 估算约 0.015 CU。原始 SAR/SFMR 未拉回 工作站。',
'审核说明：主程序初次 `nearest_km` 是峰值筛选时 5–120 km 窗口内的截断最小值，不能代表实际穿眼最近点；本表使用 `audit_nearest.py` 对整个半腿重新提取的 `true_nearest_km`，初始文件原样保留。逐腿质量与原始窗口细节见 `sfmr_legs_vdm.json`。']
p=R/'官方VDM_SFMR结构对照_第二轮.md'
with p.open('x') as f:f.write('\n'.join(out)+'\n')
print(p,'groups',len(G),'legs',sum(len(x['leg_details']) for x in G),'median',statistics.median(v))
