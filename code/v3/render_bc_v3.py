#!/usr/bin/env python3
"""Render L26.18 v3 numerics from downloaded Colab JSON, no raw fields."""
import json,pathlib,statistics
R=pathlib.Path(__file__).resolve().parent
F=R/'colab_final'
rows=json.loads((F/'sar_results.json').read_text()); groups=json.loads((F/'sfmr_comparison.json').read_text()); legs=json.loads((F/'sfmr_legs.json').read_text())['legs']
assert len(rows)==11 and len(groups)==9
assert sum(len(g['indices']) for g in groups)==11
fmt=lambda x,n=3:'—' if x is None else f'{x:.{n}f}'
lines=['# L26.18 v3 SAR 结构量及 SFMR 观测逐景对照','', '数据来源：IFREMER CyclObs 2026 L2M 网格风速 NetCDF；NOAA/AOML ERDDAP `sfmr_2018_2022`。原始 SAR、SFMR 均只在 Colab CPU 临时会话下载，未拉回 工作站。逐景 SHA-256、格距与边界截断见 `colab_final/sar_results.json`。', '', '主读法复用 L26.18-01：quality_level≥3、rejection_flag=0；3 km 环、0–200 km 有效像元等权平均峰环；覆盖率为 0–2RMW 有效 10° 方位扇区数/36；八向变体为中心附近各偏移一像元；有效方位变体为峰环覆盖率≥80%；CyclObs rmax 单列。波数1系 0.5–1.5RMW 扇区均风的一阶幅度/均风。相对变化为 |变体−主读法|/主读法。','', '| # | 风暴／采集 UTC | CyclObs 中心及质量旗 | 0–2RMW 覆盖率 | RMW 主读法 km | ≥80% 方位 km | rmax km | 八向偏移 km (dj,di) | 最大相对变化 | 波数1/均风 |', '|---|---|---|---:|---:|---:|---:|---|---:|---:|']
for a in rows:
 sh='; '.join(f"({s['dj']:+d},{s['di']:+d}) {fmt(s['rmw_km'],1)}" for s in a.get('shift_8',[]))
 flag=a.get('center_quality_flag_api') or '未给'
 cen=a.get('center_lat_lon')
 loc='—' if not cen else f'{cen[0]:.4f}N,{cen[1]:.4f}E'
 lines.append(f"| {a['index']+1} | {a['storm']} {a['time_utc']} | {a['center_source']} {loc}; {flag} | {fmt(a.get('coverage_0_2rmw'))} | {fmt(a['rmw_km'],1)}{' (边界截断)' if a.get('winning_ring_truncated') else ''} | {fmt(a.get('rmw_80_km'),1)} | {fmt(a.get('analysis_rmax_km'),1)} | {sh} | {fmt(a['max_relative_change'])} | {fmt(a.get('wave1_fraction'))} |")
v=[a['max_relative_change'] for a in rows if a['max_relative_change'] is not None]
lines+=['',f'逐景最大相对变化：'+', '.join(f"{a['storm']} {a['time_utc']}={fmt(a['max_relative_change'])}" for a in rows)+f'。主读法可算景中位数 {fmt(statistics.median(v))}（{len(v)} 景）。','', 'SFMR：FLAG=0、NGC≥4、SWS≥0；11 点约 10 s 平滑；独立航迹风速极小点为中心代理，跨同风暴中心按时间线性插值；穿眼近点≤15 km、离眼≥70 km、风速峰半径≥10 km；每时刻 ±3 h 合格腿峰半径中位为 RMW_obs。不是官方 vortex fix。无 b-deck/BEST/ATCF 中心或对照。两景同一时刻的 SAR RMW 先取中位。相对差=|SAR−obs|/obs。','', '| 风暴／时刻 UTC | SAR 景 # | SFMR 合格腿数 | 合格航班 | RMW_obs km | SAR RMW km | 相对差 |','|---|---|---:|---|---:|---:|---:|']
for g in groups:
 lines.append(f"| {g['storm']} {g['time_utc']} | {','.join(str(i+1) for i in g['indices'])} | {g['qualifying_legs']} | {','.join(g['flight_ids']) or '—'} | {fmt(g['rmw_obs_km'])} | {fmt(g['rmw_sar_km'],1)} | {fmt(g['relative_difference'])} |")
w=[g['relative_difference'] for g in groups if g['relative_difference'] is not None]
lines+=['',f'有合格独立观测的时刻数 {len(w)}/{len(groups)}；相对差中位数 {fmt(statistics.median(w) if w else None)}。逐腿半径与时间、中心候选见 `colab_final/sfmr_legs.json`、`colab_final/sfmr_centers.json`。']
(R/'结构对照表_v3_SAR_SFMR.md').write_text('\n'.join(lines)+'\n')
print('REPORT_DONE',len(rows),len(groups),'sensitivity_median',statistics.median(v),'eligible_times',len(w),'obs_median',statistics.median(w) if w else None)
