#!/usr/bin/env python3
"""Render r2 benchmark summary from actual machine scores."""
import json
from pathlib import Path
r=Path(__file__).resolve().parent
d=json.loads((r/'metrics_r2.json').read_text())
labels={'idw':'IDW²','ok75':'OK 固定75 km','okfit':'OK 每小时变差拟合','era':'ERA5 直接','era_resok':'ERA5＋残差OK','gbt':'GBT（仅ERA5）','gbt_resok':'GBT＋交叉拟合残差OK'}
f=lambda x:f'{x:.3f}'
lines=['# H r2：稀疏站网风速重建（UTC；独立新结果）','','## 判据与结论','事先判据：平均最近输入站距离 ≥50 km 的稀疏档，最优 ERA5 融合/学习法相对最优纯插值 RMSE 至少下降20% 且 ≥2/3 检验站改善，才判“稀疏处值得”；10–20% 判“有条件”；<10% 判“插值够用”。最稀疏的 10% 档：输入14站，检验122站/次；平均最近距离81.82 km，纯插值 IDW RMSE 1.948，ERA5＋残差OK 1.687 m/s，下降13.40%，跨20次重抽汇总的逐站126/136改善。故判“有条件”，而非“稀疏处值得”。25% 档虽也达到50 km，收益仅8.84%，说明结论依赖稀疏程度；ERA5站点同化情况仍待核，非严格独立背景验证。','','## 输入与评估口径','完全复用 r1 的 observations_qc2.csv.gz、10 个选定 UTC 日期和各日 ERA5 CSV；不取新数据。去掉与 AUS 重复的 BSM，实际有小时观测的136站；各档固定种子314159、20次随机站点重抽，输入站数为68/34/14。各次只在输入站的观测训练/拟合；检验站全时段观测从未进入拟合与变差函数。每小时有效观测站随报文变化，平均距离以实际被评分站时、当时有效输入站计。METAR 持续/平均风速（ASOS通常为2分钟平均），不是阵风或整小时均值；时间以UTC对齐。各方法在同档内同一检验站时评分；重复抽样的站时非独立新观测。','','## 各稀疏档总体对比（m/s）','| 输入比例/站数 | 平均最近距 km | 检验站时（20次总数） | 方法 | RMSE | MAE | 偏差 |','|---|---:|---:|---|---:|---:|---:|']
for frac in ('0.5','0.25','0.1'):
 z=d['fractions'][frac]
 for m,v in z['methods'].items():lines.append(f"| {int(float(frac)*100)}% / {round(float(frac)*d['n_unique_stations'])} | {z['mean_nearest_km']:.2f} | {z['n']} | {labels[m]} | {f(v['rmse'])} | {f(v['mae'])} | {v['bias']:+.3f} |")
lines+=['','| 输入比例 | 最佳纯插值 | 最佳融合/学习 | RMSE 改善 | 逐站改善（跨重复合并每站受检记录） |','|---|---|---|---:|---:|']
for frac in ('0.5','0.25','0.1'):
 z=d['fractions'][frac];lines.append(f"| {float(frac):.0%} | {labels[z['best_interpolation']]} | {labels[z['best_fusion']]} | {z['gain']:.2%} | {z['station_wins']}/{z['station_total']} |")
lines+=['','## 实际观测日峰值时刻的误差','每个重复×受检站×UTC日只取观测最大风速对应小时，比较该时刻预测值（不是预测日最大值）；负偏差为低估。','| 输入比例 | 站-日-重复数 | 方法 | 峰值时刻 RMSE m/s | 偏差 m/s |','|---|---:|---|---:|---:|']
for frac in ('0.5','0.25','0.1'):
 z=d['fractions'][frac]
 for m,v in z['peak_at_observed_hour'].items():lines.append(f"| {float(frac):.0%} | {z['peak_n']} | {labels[m]} | {f(v['rmse'])} | {v['bias']:+.3f} |")
lines+=['','## 站点周边下垫面分组','复用 r1 ESA WorldCover 2021 v200 的站点 1 km 主类：50=建成区，其余非建成区（不是测风仪现场暴露评级）。BSM剔除后，建成区15站、非建成区121站；站点受检次数有差异。','| 输入比例 | 分组 | 站数 | 被检站时 | 最佳总体纯插值 RMSE | 最佳总体融合 RMSE |','|---|---|---:|---:|---:|---:|']
for frac in ('0.5','0.25','0.1'):
 z=d['fractions'][frac]
 for group,v in z['landcover'].items():lines.append(f"| {float(frac):.0%} | {'建成区' if group=='built_majority_class' else '非建成区'} | {v['n_station']} | {v['n_samples']} | {f(v['methods'][z['best_interpolation']]['rmse'])} | {f(v['methods'][z['best_fusion']]['rmse'])} |")
lines+=['','## 参数来源与预设假设','| 参数 | 值、来源与含义 |','|---|---|','| 风、日期、ERA5 | 原 r1 `results_r1.md` 与 `dates_qc2.md`；IEM METAR 小时持续风，ARCO-ERA5 10 m u/v 站点插值。原 QC2 >40 kt 的排除规则是 r1 假设。ERA5 对陆地地面站是否同化：待核。 |','| 站点抽稀 | 假设：136站（删 BSM 留 AUS），固定种子314159，不分层随机抽20次/档，round(比例×站数)，每档仅测试非输入站。 |','| IDW | 假设，承袭r1球面距离平方反比。 |','| OK 固定 | 假设，承袭r1指数协方差75 km、相对 nugget 0.08、常数未知均值；只用当小时输入站。 |','| OK 每小时拟合 | 假设：用当前小时输入站风速两两半平方差按25 km、最大300 km分箱；≥4对/箱，至少3箱；经验半变差拟合 sill×(1.08−exp(−h/r))，sill 取该小时输入站方差，r 限20–300 km，缺箱回退75 km；nugget 固定0.08。所有参数由输入站决定，范围中位数 '+f(d['fit_range_median_km'])+' km，回退 '+str(d['fit_range_fallback_hours'])+' 站网-小时。 |','| 背景＋残差 | ERA5 直插或 ERA5+输入站观测减去ERA5后的75 km残差OK。 |','| GBT | 假设沿用r1：80树、12叶、学习率0.06、L2=5；特征 ERA5 u/v、高程（缺失用本数据中位数）、经纬度、UTC小时sin/cos；无HRRR。训练仅输入站所有所选日。 |','| GBT＋残差 | 假设：输入站固定随机二分，两模型各从另一半站训练，形成每一输入站严格站点留出的交叉拟合残差；检验站由全输入站训练的GBT预测，再加75 km残差OK。 |','| 下垫面 | 复用r1已取 ESA WorldCover 2021 v200；站点周边1 km众数50为建成区，其余非建成区，2020年的代表性有时差。 |','','## 局限与可复现性','重复分站在同一10日气象场上，不是跨年份独立检验；没有把重抽站时视作独立样本来报显著性。136站中有些只短时有效，20次评估逐站赢数按该站被抽成检验站时的全部误差汇总。小时经验变差函数在小样本时不稳，固定 nugget/sill 与范围上下限属于假设而非文献给定；地形、机场暴露和模式/站点代表性误差混合。ERA5 对地面站的同化口径待 Lead 核，不能宣称独立无信息。纯站点抽稀不模拟站网布设的空间相关选择，且极端无站地区未作网格真值验证。','数据源：Iowa Environmental Mesonet/Iowa State University 归档 METAR 与 TX_ASOS 元数据；Hersbach et al. (2020) ERA5, DOI 10.1002/qj.3803，经 Google Research ARCO-ERA5；ESA WorldCover Consortium (2022), DOI 10.5281/zenodo.7254221。均已在 `22_Lab/PUBLIC_CITATIONS.md` 第130–133、148–149行登记，本轮不新增外部数据/代码。图 `rmse_distance_r2.png` 标出观测与 ERA5 来源；脚本 `evaluate_r2.py`、`report_r2.py`。','','## 一句话判据','10%输入站档最近距离81.82 km时 ERA5＋残差OK 比最佳纯插值 RMSE 低13.40%，126/136站改善，按事先判据“有条件”；25%档仅降8.84%，不可笼统称稀疏处值得。','']
(r/'results_r2.md').write_text('\n'.join(lines),encoding='utf-8')
print('results_r2.md',len(lines),'lines')
