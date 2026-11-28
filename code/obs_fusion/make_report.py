#!/usr/bin/env python3
"""Write corrected provenance-rich report without replacing earlier exploratory outputs."""
import json
from pathlib import Path
import pandas as pd
R=Path(__file__).resolve().parent
M=json.loads((R/'metrics_r1_clean.json').read_text());obs=pd.read_csv(R/'observations_qc2.csv.gz')
days=set(M['dates']);subset=obs[obs.date.isin(days)]
aggregate=subset.groupby('date').agg(stations=('station','nunique'),hours=('speed','size'),fraction8=('speed',lambda x:(x>=8).mean())).sort_index()
date_text=['# 日期与筛选（QC2；本文件替代初始 dates.md 的计数）','','规则：候选站点经纬度 28–34°N、94–100°W；2020-11–2021-03 UTC 日至少 60 站、小时风速 ≥8 m/s 比例 ≥10%、区域 METAR 主体无 TS/VCTS/CB、NOAA Storm Events 整个 Texas 当地日期无 Thunderstorm Wind；极端异常 METAR 风速 >40 kt 排除（假设的保守 QC）。选中全部 10 天，未因结果改日期。','','| UTC 日期 | 站数 | 有效观测 | ≥8 m/s 比例 |','|---|---:|---:|---:|']
for d,r in aggregate.iterrows():date_text.append(f'| {d} | {int(r.stations)} | {int(r.hours)} | {r.fraction8:.2%} |')
date_text+=['','数据：IEM TX_ASOS https://mesonet.agron.iastate.edu/request/download.phtml?network=TX_ASOS ； NOAA Storm Events https://www.ncei.noaa.gov/access/storm-events-database/bulk-data 。原 METAR 仅作筛选，不能证明无对流。']
(R/'dates_qc2.md').write_text('\n'.join(date_text)+'\n')
name={'idw':'IDW²','ok':'普通克里金','era':'ERA5 直接','hrrr':'HRRR f01 直接','era_resok':'ERA5 + 残差 OK','hrrr_resok':'HRRR f01 + 残差 OK','gbt':'梯度提升树','gbt_resok':'梯度提升树 + 残差 OK'}
lines=['# H 良态风站点留一重建 r1：QC2 有效结论','','本文件以 `metrics_r1_clean.json` 和 `comparison_r1_clean.png` 为有效结果。首次计算的 `metrics_r1.json`、`comparison_r1.png` 和 `predictions_r1.csv.gz` 含三条畸形 METAR（GYI 134 kt、CNW 两条 121 kt），**作废、勿引用**；遵守不覆盖既有结果的约束而保留。`dates.md` 是 QC 前初稿，修订计数见 `dates_qc2.md`。','',
'## 判据与一句话结论','','事先判据：最好的背景+残差或学习方法相对 IDW/OK 较优者 RMSE 至少降低 20% 且至少 2/3 站改善 → 值得继续；10–20% 或仅一项 → 有条件；小于 10% → 插值够用。此筛选不等于论文结论。',
f"总体：OK {M['methods']['ok']['rmse']:.3f} m/s；最优梯度提升树+残差 OK {M['methods']['gbt_resok']['rmse']:.3f} m/s，下降 {M['gain']:.2%}（逐日 bootstrap 95% 区间 {M['gain_ci95'][0]:.2%}–{M['gain_ci95'][1]:.2%}）；改善 {M['station_wins']}/{M['station_total']} 站，未达到 2/3。按事先判据：插值够用；但 >50 km 稀疏站距子组增益值得另行检验。",'',
'## 样本、数据、方法','','10 个良态大风 UTC 日、240 小时、137 个实际受评站、31,898 站时样本；145 个候选站。最近站距按该小时有有效观测的其它站计算。所有分数使用完全相同的目标站小时集合。地面小时真值为最近整点 ±30 min METAR（非 1-min 平均）；knots × 0.5144444444444445；仅去除站点值超过 40 kt 的明显畸形报文，未修改其它报文。IEM 声明其原始归档只做有限 QC。[1]','',
'ERA5 从 Google Research ARCO-ERA5 0.25° 小时 10 m U/V Zarr 对站点双线性插值；HRRR 从 NOAA AWS S3 `wrfsfcf01` 10 m U/V GRIB2 消息按字节范围取数，用网格最近点；目标 UTC 小时使用前一小时初始化的 f01，不使用 f00。[2][3]','',
'IDW 用球面距离 1/d²；OK 对当小时其它站建指数协方差 C(d)=exp(-d/75 km)，对角加 0.08 nugget，常数未知均值约束；矩阵逆对角恒等式一次求所有单站严格 LOO 预测。背景+残差对每小时其它站的“观测风速 - 该站模式风速”做同一 OK。学习法 HistGradientBoostingRegressor 对每一个待检站单独训练，跨全部十日严格排除该站，特征 ERA/HRRR U/V、站点高程、经纬度、小时正余弦；加残差 OK 时对其它站模型训练内的残差做当小时 OK。GBDT 参数是预先固定的小模型，未调参。风速独立建模，故学习法无 u/v/风向预测。','',
'## 总体方法对比（m/s）','','| 方法 | RMSE | 逐日 bootstrap 95% CI | MAE | 偏差 | 每站每日实际峰值时刻 RMSE |','|---|---:|---:|---:|---:|---:|']
for k,v in M['methods'].items():
 peak=M['peak'][k]
 lines.append(f"| {name[k]} | {v['rmse']:.3f} | [{v['rmse_ci95'][0]:.3f}, {v['rmse_ci95'][1]:.3f}] | {v['mae']:.3f} | {v['bias']:+.3f} | {peak['rmse']:.3f} |")
lines+=['','峰值列取每站每天观测最强小时该时刻的预测误差，1,349 站日；不是“预测日最大值 vs 观测日最大值”。最优 GBT+残差 OK 对峰值时刻偏差 '+f"{M['peak']['gbt_resok']['bias']:+.3f} m/s，明显低估。",'',
'## 最近站距与副指标','','| 目标到最近训练站 | 样本数 | OK RMSE | GBT+残差 OK RMSE |','|---|---:|---:|---:|']
for k,v in M['nearest_distance'].items(): lines.append(f"| {k} km | {v['n']} | {v['baseline_rmse']:.3f} | {v['best_rmse']:.3f} |")
lines+=['','风向与矢量指标仅对有效风向、且当小时全部参与站都有数值的 20,339 站时计算；学习法未做矢量版。风向误差按圆周差绝对值，平静风向未特别筛除。','', '| 方法 | u RMSE (m/s) | v RMSE (m/s) | 风向 MAE (°) |','|---|---:|---:|---:|']
for k,v in M['secondary'].items():lines.append(f"| {name[k]} | {v['u_rmse']:.3f} | {v['v_rmse']:.3f} | {v['direction_mae_deg']:.2f} |")
lines+=['','## 逐站 LOO 风速误差（m/s）','','下表按站列全量 137 站；JSON 还给每个方法逐站 RMSE/MAE/偏差和 31,898 行原始留一预测，分别见 `metrics_r1_clean.json` 与 `predictions_r1_clean.csv.gz`。','','| 站 | n | OK RMSE | ERA+残差 OK | HRRR+残差 OK | GBT | GBT+残差 OK |','|---|---:|---:|---:|---:|---:|---:|']
for s,v in M['station'].items(): lines.append(f"| {s} | {v['ok']['n']} | {v['ok']['rmse']:.2f} | {v['era_resok']['rmse']:.2f} | {v['hrrr_resok']['rmse']:.2f} | {v['gbt']['rmse']:.2f} | {v['gbt_resok']['rmse']:.2f} |")
lines+=['','## 参数来源与可疑点','','| 参数 | 取值 | 来源或假设 |','|---|---|---|','| 站点地理范围、观测单位 | 28–34°N，94–100°W；knots | 任务书；IEM API 字段定义[1] |','| METAR 整点代表 | 最近整点 ±30 min | 假设，日内标准 METAR 多在 :53–:55；与逐时再分析配准 |','| 强风日阈值及无对流排除 | ≥10% 站时 ≥8 m/s，≥60 站，区域 METAR 无 TS/VCTS/CB、全州 Storm Events 无 Thunderstorm Wind | 任务书“相当比例”未给数，10% 为事先固定假设；NOAA 数据源[4] |','| 极端风 QC | >40 kt 排除 | 假设；三条异常原文 `160134KT`/`140121G18KT` 不合常理，超过并伴错误格式；仅排这三条，低风速和其他潜在误码未进一步处理 |','| HRRR 时效 | f01，目标小时前一小时初始化 | 任务书禁止 f00；AWS idx 实测包含 `1 hour fcst`，脚本可核对[3] |','| HRRR 站点映射 | 网格最近邻 | 假设；避免 Lambert 网格重网格插值；会留下几 km 代表性误差 |','| IDW 幂 | 2 | 假设，经典距离平方反比，不做事后优化 |','| OK 变差函数/相关长 | 指数，75 km，nugget 0.08 | 均为预先固定假设；**未按日/小时拟合经验变差函数，不完全满足任务书此项**；同样作用于纯 OK、背景残差 OK、学习残差 OK，结果对长尺度敏感 |','| GBT 超参 | 80 树、12 叶、学习率 0.06、L2=5 | 假设的小 CPU 模型；不以验证集调参，避免站点泄漏 |','| 自助法 | 10 日有放回抽样 2000 次，随机种子 2718 | 假设；日数少，相邻天气过程相关，区间可能偏窄 |','',
'## 局限与后续判断','','1. ERA5 是再分析、可能含同一观测网络历史同化；HRRR f01 虽非同小时 f00，同化的前一小时站点资料仍可能影响该预报；两者都不是严格“完全无站点信息”的独立背景。','2. GBT 使用同一天其他站观测训练，实际对待检站全十天保持完全隔离；“GBT+残差”在训练站上用模型的训练内残差，非交叉拟合，可能乐观。','3. 未按日/小时拟合变差函数，也未扫描 IDW 幂次；这限制“最好的纯插值”称谓，只能说比较了两个预先固定的强基线。>50 km 子组占少数且地形/站型组成可能不同；不能从该子组推断普适增益。','4. 高程来自 IEM 站表，未引入真实 NLCD；METAR 实际传感器高度未逐站核证为 10 m；风速以整数 knot 报告、非小时平均。','5. 筛选依据 METAR + 已登记雷暴风，仅排除显见对流；Storm Events 以当地日期而 METAR 以 UTC 日筛选，跨日边界可能残余误分类。','6. 更完整的后续：训练站互斥的日/站变差函数敏感性、严格无站同化背景、按日期外推验证以及每日最大值指标。当前按预定总体判据不建议直接扩大到全域融合项目。','',
'## 数据来源与复现','',
'[1] Iowa Environmental Mesonet, TX_ASOS GeoJSON 与 METAR 归档，https://mesonet.agron.iastate.edu/geojson/network.py?network=TX_ASOS ; https://mesonet.agron.iastate.edu/request/download.phtml?network=TX_ASOS 。',
'[2] Hersbach et al. (2020), ERA5, https://doi.org/10.1002/qj.3803 ; Google Research ARCO-ERA5，https://github.com/google-research/arco-era5 。',
'[3] NOAA/NCEP HRRR AWS 公开桶，https://registry.opendata.aws/noaa-hrrr-pds/ ; Herbie index/range 文档 https://herbie.readthedocs.io/en/stable/user_guide/tutorial/inventory.html 。',
'[4] NOAA NCEI Storm Events 年度 details，https://www.ncei.noaa.gov/access/storm-events-database/bulk-data 。',
'重跑步骤：`fetch_obs.py`（已保存原始归档；运行将覆盖既有原始文件，请勿在未经许可时执行）、`screen_dates.py`（同理，当前 QC2 输出已存在）、`fetch_background.py`（会跳过现有日期背景 CSV）、`evaluate.py`（当前 QC2 输出已存在，重跑需要另设新文件名）。图 `comparison_r1_clean.png` 数据来源同 [1]–[3]。']
(R/'results_r1.md').write_text('\n'.join(lines)+'\n')
print('report',len(lines),'rows',len(M['station']))
