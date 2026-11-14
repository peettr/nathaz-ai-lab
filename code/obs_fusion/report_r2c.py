#!/usr/bin/env python3
"""Report cleaned sparse-network experiment; does not alter r1/r2 outputs."""
import json
from pathlib import Path
R=Path(__file__).resolve().parent
m=json.loads((R/'metrics_r2c.json').read_text())
c=json.loads((R/'r1clean_r2c.json').read_text())
labels={'idw':'IDW p=2','ok75':'OK 固定75 km','okfit':'OK 每小时拟合','era':'ERA5 直接','era_resok':'ERA5+残差OK 固定75 km','era_resokfit':'ERA5+残差OK 每小时拟合','gbt':'GBT ERA5','gbt_resok':'GBT+交叉拟合残差OK'}
def verdict(z):
 gain=z['gain'];win=z['station_wins']/z['station_total']
 if gain<.10:return '插值够用'
 if gain>=.20 and win>=2/3:return '稀疏处值得'
 return '有条件'
L=['# H r2-clean：清洗站点后的稀疏站网重算（UTC）','','本报告按审查 2598bcfe 裁决重算；所有源文件只读，结果用 r2c 新文件名，非原 r2 覆盖。观测为 IEM METAR 小时报的持续风速（通常2分钟平均），非整小时均值或阵风；背景为 ARCO-ERA5 10 m u/v。只用 r1 的10个既定 UTC 日、QC2 观测（>40 kt 排除是 r1 假设）与 ERA5 缓存。','','## 事先判据与结果','在平均实际最近输入站距≥50 km 的每档，最佳 ERA5 融合/学习相对最佳 IDW/OK RMSE 降≥20% 且≥2/3 受检站更好→“稀疏处值得”；10–20% 或只满足一门槛→“有条件”；<10%→“插值够用”（按降幅优先分档）。纯插值与融合各自在本档选最优；不拿两个变差版本中较弱者作基线。','','| 输入档 | 当小时实际最近输入站距 km（站时加权；重抽均值±SD） | 纯插值最优 RMSE m/s | 融合最优 RMSE m/s | 降幅 | 改善站数 | 判定 |','|---|---:|---:|---:|---:|---:|---|']
for f in ('0.5','0.25','0.1'):
 z=m['fractions'][f];base=z['best_interpolation'];best=z['best_fusion'];L.append(f"| {float(f):.0%} | {z['mean_nearest_km']:.2f}（{z['redraw_distance_mean_km']:.2f}±{z['redraw_distance_sd_km']:.2f}） | {z['methods'][base]['rmse']:.3f}（{labels[base]}） | {z['methods'][best]['rmse']:.3f}（{labels[best]}） | {z['gain']:.2%} | {z['station_wins']}/{z['station_total']} | {verdict(z)} |")
L+=['','25%与10%档分别判定，50%档亦展示作参照。跨20次重抽，RMSE 将该档所有被检站时误差平方合并后开方，并非20个 RMSE 的算术平均；每站仅在其被抽为检验站的重复中合并该站误差，再比较最优方法的逐站RMSE，一站计一票。站时与重复共享同一批天气，不当独立样本。最近站距每个评分小时以当时确有观测的输入站算，不以名义站表算。','','## 各方法对比（RMSE/MAE/有符号偏差，m/s）','| 输入档 | 检验站时 | 方法 | RMSE | MAE | 偏差 |','|---|---:|---|---:|---:|---:|']
for f in ('0.5','0.25','0.1'):
 z=m['fractions'][f]
 for key,v in z['methods'].items():L.append(f"| {float(f):.0%} | {z['n']} | {labels[key]} | {v['rmse']:.3f} | {v['mae']:.3f} | {v['bias']:+.3f} |")
L+=['','## r1 全站留一清洗版','只比较原 r1 的固定75 km OK 与固定75 km ERA5+残差 OK；对每个小时构造增广普通克里金矩阵，解析 LOO 严格排除目标站观测；所有异常站在矩阵构造前剔除。','| 有效站时 | 站数 | OK RMSE | ERA5+残差OK RMSE | 降幅 | 改善站数 |','|---:|---:|---:|---:|---:|---:|',f"| {c['n']} | {c['n_stations']} | {c['ok75_rmse']:.3f} | {c['era_resok_rmse']:.3f} | {c['gain']:.2%} | {c['station_wins']}/{c['station_total']} |",'','## 清洗规则与剔除清单','先剔 WorldCover 站点周围1 km 主类80（水体）的 BQX（Brazos 451，海上平台）、GVW（Galveston 209B，海上平台）；剔除与 CVB 坐标完全重合且坐标可疑的 T89。再对所有站两两球面距离 <2 km 的站对只留一站：AUS/BSM（1.600 km；同样有效站时，保留主要机场 AUS）、F12/RFI（0 km，F12 该批无有效观测，留 RFI）、5R3/RYW（0.446 km，5R3 该批无有效观测，留 RYW）、CVB/T89（0 km，T89 因可疑先剔，留 CVB）。保留站重算全部随机抽样、输入/检验、训练、变差拟合，剔除站绝未用作输入或评分；已通过清洗后站间最小距离≥2 km 断言。','','## 峰值时刻与下垫面','下表的峰值仅为每个站×UTC日×重抽中观测最大风速所在时刻的预测误差（不是模型自己预测的日最大值）；偏差为预测减观测。','| 输入档 | 峰值样本 | 方法 | RMSE | 偏差 |','|---|---:|---|---:|---:|']
for f in ('0.5','0.25','0.1'):
 z=m['fractions'][f]
 for key in [z['best_interpolation'],z['best_fusion']]:
  v=z['peak_at_observed_hour'][key];L.append(f"| {float(f):.0%} | {z['peak_n']} | {labels[key]} | {v['rmse']:.3f} | {v['bias']:+.3f} |")
L+=['','WorldCover 2021 v200 站点周围1 km 主类50划为建成区，其余非建成区，仅代表周边下垫面，不代表测风仪现场暴露。','| 输入档 | 分组 | 站数 | 站时 | 最佳纯插值RMSE | 最佳融合RMSE |','|---|---|---:|---:|---:|---:|']
for f in ('0.5','0.25','0.1'):
 z=m['fractions'][f]
 for k,v in z['landcover'].items():L.append(f"| {float(f):.0%} | {'建成区' if k=='built_majority_class' else '非建成区'} | {v['n_station']} | {v['n_samples']} | {v['methods'][z['best_interpolation']]['rmse']:.3f} | {v['methods'][z['best_fusion']]['rmse']:.3f} |")
L+=['','## 参数来源表','| 参数 | 来源/性质 |','|---|---|','| 观测、日期、ERA5 | 沿用 r1 `results_r1.md`、`dates_qc2.md`、本地 QC2/ERA5 文件；METAR 逐小时采样的持续风、UTC。ERA5 陆地10m风不直接同化该站（见审查裁决），仍不等于所有上游信息完全独立。 |','| 剔除规则 | 审查2598bcfe裁决：水体主类、可疑同坐标、<2 km去重；有效观测较多者优先，同数 AUS 优先。 |','| 站网 | 假设沿用 r2：随机种子314159，每档20次，不分地理层，输入比例50/25/10%，Python round 取整。 |','| IDW | 假设沿用 r1/r2，球面距离反平方。 |','| 固定 OK | 假设沿用 r1/r2：指数协方差75 km、相对 nugget=0.08、未知常数均值。 |','| 每小时拟合 OK | 假设沿用 r2：当小时输入站两两半平方差，25 km 距离箱，最高300 km；每箱≥4对且≥3箱，固定该小时输入站方差为 sill，拟合 exp 范围20–300 km，不足退回75 km；纯插值用原观测拟合，融合用观测减ERA5的残差拟合。原场回退 '+str(m['fit_range_fallback_hours'])+' 次、中位范围 '+f"{m['fit_range_median_km']:.1f}"+' km；残差回退 '+str(m['resfit_fallback_hours'])+' 次、中位范围 '+f"{m['resfit_median_km']:.1f}"+' km。 |','| GBT与交叉拟合 | 沿用r2假设：80迭代、12叶、学习率.06、L2=5，特征ERA5 u/v、高程、经纬度、UTC小时sin/cos；残差严格按输入站二折交叉拟合；无HRRR。 |','| 下垫面 | 复用 r1 ESA WorldCover 2021 v200 站点1 km主类；50建成，其余非建成；2020日与影像年份不完全同年。 |','','## 局限与文件','2020–21的10个筛选良态风日、一次随机种子、同一站反复受检；“改善站数”不是独立新站。经验变差范围及残差适用性不是文献推荐值，未做嵌套调参；仍可能有站点代表性误差。ERA5背景虽不直接同化陆地10m风，仍可能间接受同化系统影响。未验证阵风、损失点或网格真值。','来源：IEM METAR、Hersbach et al. 2020 ERA5 DOI 10.1002/qj.3803、ESA WorldCover Consortium 2022 DOI 10.5281/zenodo.7254221，均已列于 `22_Lab/PUBLIC_CITATIONS.md`；本轮没有新增外部数据。脚本 `evaluate_r2c.py`、`evaluate_r1clean_for_r2c.py`、`report_r2c.py`；图 `rmse_distance_r2c.png`。','',f"## 结论\n25%档 {verdict(m['fractions']['0.25'])}；10%档 {verdict(m['fractions']['0.1'])}。只适用于本次清洗站网和持续风留出站检验。",'']
assert not (R/'results_r2c.md').exists(),'Refusing to overwrite r2c result'
(R/'results_r2c.md').write_text('\n'.join(L),encoding='utf-8')
print('report lines',len(L))
