#!/usr/bin/env python3
"""Render concise E report from measured Colab outputs only; never fill missing methods with zero."""
import json,csv,statistics
from pathlib import Path
P=Path('./22_Lab/06_Logs/e_terrain')
m=json.loads((P/'metrics.json').read_text());strong=list(csv.DictReader((P/'strong_metrics.csv').open()));full=list(csv.DictReader((P/'full_metrics_baselines.csv').open()))
sites=list(csv.DictReader((P/'stations_frozen.csv').open()));terrain={x['station']:x['terrain'] for x in sites}
def mean(xs):return sum(xs)/len(xs) if xs else None
def fmt(x):return '—' if x is None else f'{float(x):.2f}'
lines=['# E 瑞士冷季复杂地形预警：最小示范结果','',f"站表在 {m['frozen_at_us_eastern']} 冻结，且早于首次预报误差计算。Source: MeteoSwiss; NOAA AIWP; NOAA GFS。",'']
lines+=['## 判据与口径','',"冷季 2023-10-01—2024-03-31 全部 10 分钟有效风速求每站 P95/P99；预报 00/12 UTC 起报，24/48 h 有效时刻与观测 10 分钟结束时刻同一 UTC 时间戳（例如 00:00 是 23:50:01–00:00:00 的均风），不同提前量不混淆。强风=观测≥冷季 P95；10–12 月拟合按站×源×提前量的线性 MOS（非负截断），1–3 月检验；所有三法按四预报源共同有效的站×起报×提前量配对。WindNinja 仅在观测强风时次运行，因此不能计算它的全时次 MAE 和完整误报率。",'',"冻结主判据：WindNinja 或 FuXi-CFD 相对双线性插值的强风站点 MAE 中位降幅≥15%，在≥2/3 站胜出，同时不输于 MOS。这里把“不输于 MOS”操作化为同一配对样本上站点 MAE 中位数比较；若需不同汇总口径请保留冻结规则并报告这一歧义，不按结果挑选。",'']
lines+=['## 冻结站点与观测覆盖','', '|站|类别|经纬度|海拔 m|测风高度 m|冷季完整率|官方地形描述/选择理由|','|---|---|---|---:|---|---:|---|']
for x in sites:lines.append(f"|{x['station']}|{x['terrain']}|{x['lat']}, {x['lon']}|{x['elevation_m']}|{x['wind_sensor_height_m']}|{float(x['coldseason_10min_completeness']):.1%}|{x['selection_reason']}|")
lines+=['',"注：高原一类是高海拔开阔平地的代理，MeteoSwiss 官方 exposure 为 plain，并未独立证实地貌学上的‘高原’；测风高度在官方站元数据未见逐站字段，均为 unverified，不擅自写 10 m。",'']
lines+=['## 冻结判据检验','',f"归档预报对象 {m['forecast_objects']}/{m['forecast_expected']}，缺失 {len(m['missing_objects'])} 个（见 metrics.json）；强风配对 {m['strong_cases']} 条，WindNinja 成功 {m['wn_success_cases']} 条、失败 {m['wn_errors']} 条。",f"站点强风 MAE 相对双线性降幅中位 {fmt(m['median_station_reduction_pct'])}%；胜出 {m['stations_wn_better_bilinear']}/12 站（要求≥8）；WindNinja 与 MOS 的站点 MAE 中位分别 {fmt(m['median_station_wn_mae_ms'])} 与 {fmt(m['median_station_mos_mae_ms'])} m/s（越小越好）；WindNinja 在 {m['stations_wn_not_worse_mos']}/12 个单站不差于 MOS。",'']
if m['pass_gate'] is True: verdict='过：WindNinja 满足三项门槛；FuXi-CFD 未进入主判。'
elif m['pass_gate'] is False:verdict='WindNinja 不过；FuXi-CFD 尚未完成瑞士站评测，整个“任一方法”主判据目前未判定，不得宣称总体不过。'
else:verdict='未判定：WindNinja 运行不完整，不能对冻结主判据作过/不过断言。'
lines+=['判定：'+verdict,'']
lines+=['## 逐站、逐源、逐提前量强风指标','',"同一行三法是相同的强风时次；每格为 MAE / 偏差（m/s），偏差=预报−观测。FuXi-CFD 只通过官方样本权重验证，未做瑞士站强风分数，故不填数字。",'','|站|类别|预报源|h|n|双线性|MOS|WindNinja|FuXi-CFD|','|---|---|---|---:|---:|---:|---:|---:|---|']
d={}
for row in strong:d[(row['station'],row['source'],int(row['lead_h']),row['method'])]=row
for sid in [x['station'] for x in sites]:
 for source in ['FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS','GFS']:
  for lead in [24,48]:
   rows=[d.get((sid,source,lead,method)) for method in ['bilinear','mos','windninja']]
   if not all(rows):
    lines.append(f'|{sid}|{terrain[sid]}|{source}|{lead}|0|—|—|—|未跑|');continue
   vals=[f"{fmt(q['strong_mae_ms'])} / {fmt(q['strong_bias_ms'])}" for q in rows]
   lines.append(f"|{sid}|{terrain[sid]}|{source}|{lead}|{rows[0]['n']}|{vals[0]}|{vals[1]}|{vals[2]}|未跑|")
lines+=['','## 地形类别汇总（强风 MAE / 偏差，m/s）','','|类别|预报源|h|双线性|MOS|WindNinja|FuXi-CFD|','|---|---|---:|---:|---:|---:|---|']
for t in ['ridge','pass','valley','plateau']:
 for source in ['FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS','GFS']:
  for lead in [24,48]:
   cells=[]
   for method in ['bilinear','mos','windninja']:
    g=[x for x in strong if x['terrain']==t and x['source']==source and int(x['lead_h'])==lead and x['method']==method]
    n=sum(int(x['n']) for x in g);v=lambda k:sum(float(x[k])*int(x['n']) for x in g)/n if n else None
    cells.append(f"{fmt(v('strong_mae_ms'))} / {fmt(v('strong_bias_ms'))}")
   lines.append(f'|{t}|{source}|{lead}|{cells[0]}|{cells[1]}|{cells[2]}|未跑|')
lines+=['','## 预警次要指标（不参与判定）','',"双线性与 MOS 的全时次 MAE/偏差、99 分位命中率和误报率逐站×源×提前量在 `full_metrics_baselines.csv`。WindNinja 只在已观测强风时次求解，因缺非事件时次，不能定义其完整 99 分位误报率；仅给其在观测达到 P99 的已计算样本上的条件命中率，不等于完整检验。",f"WindNinja 条件命中率 {fmt(m['wn_event99_hit_rate_conditional'])}（P99 个数 {m['wn_event99_n']}）；完整误报率 null；全时次 MAE null。观测阵风因子（1 s 阵风/10 min 均风，均风≥1 m/s）逐站中位见 metrics.json；没有预报阵风。",'']
lines+=['## 参数来源与限制','', '|参数|取值与出处/性质|检索和约束|','|---|---|---|',
'|观测与许可|MeteoSwiss SwissMetNet 历史 2020–2029 站点 CSV，仅保留 2023-10—2024-03 10 分钟风/阵风；官方 Open Data CC-BY，重分发须 Source: MeteoSwiss|https://opendatadocs.meteoswiss.ch/a-data-groundbased/a1-automatic-weather-stations|',
'|10 分钟风与阵风|fkl010z0 (m/s, 10 分钟标量均风)；fkl010z1 (m/s, 1 秒最大阵风)|https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/ogd-smn_meta_parameters.csv；MeteoSwiss 时间戳规则 https://opendatadocs.meteoswiss.ch/general/download|',
'|测风高度|逐站未核实；不把一般 10 m 风桅高度当成逐站证据|站元数据与参数清单未列；SwissMetNet 一般站例有 10m 风桅 https://www.meteoswiss.admin.ch/dam/jcr%3Ab24af19f-c32f-464d-b2c4-163c72c8f071/SwissMetNetTheMeteoSwissReferenceMonitoringNetwork.pdf|',
'|四套预报|FOUR_v200_GFS、GRAP_v100_GFS、PANG_v100_GFS 的 NOAA AIWP HDF5 小切片 + NOAA GFS 0.25° GRIB2 idx 范围请求；参考 A1 run_forecasts.py，仅改地区窗口、日期、提前量|https://registry.opendata.aws/aiwp/ ; https://registry.opendata.aws/noaa-gfs-bdp-pds/；未整包下载|',
'|WindNinja|USFS WindNinja [地址]（conda-forge 构建；USFS 原仓库为公有领域），质量守恒 domainAverageInitialization，SRTM 1 arc-second DEM，UTM 32N 方形 30m DEM，输出 90m 格网，10m 入出风，m/s|https://github.com/firelab/windninja；https://doi.org/10.5066/F7PR7TFT；官方 CLI 选项支持 domainAverageInitialization|',
'|地形域、地表粗糙度|假设：站点周围±0.015° 近场域；vegetation=grass，30 m DEM，90 m 风格网；官方文献未给本瑞士站一一对应的域、粗糙度与网格，未做敏感性|只做可跑通的小示范，不宣称最佳设定；结果对此敏感|',
'|WindNinja 区域平均初风|假设：3 km 地形域内 0.25° 双线性风场的均值≈站点双线性矢量风；均匀、对称域的一阶 Taylor 展开支持近似，复杂曲率未验证|grid direct 试算仅单站单时次，不把它当季节敏感性结论|',
'|FuXi-CFD 官方权重|作者 Lin 等官方 Zenodo DOI 10.5281/zenodo.18770845 → HuggingFace linchensen/FuXi-CFD-model，ONNX SHA256 13daae67…；CC BY-NC 4.0，仅内部试验；官方样本推理已成功，非瑞士预测|https://zenodo.org/records/18770846 ; https://huggingface.co/linchensen/FuXi-CFD-model|',
'|FuXi-CFD 风高矛盾|arXiv 2505.12732v1 摘要写 10 m；最终作者官方 ONNX 卡片、模型签名/归一化实际是 u_100m/v_100m 9×9，与 300×300 DEM/粗糙度；按具体权重文档判为 100 m，不用 10 m 冒充|https://arxiv.org/html/2505.12732v1 ; https://huggingface.co/linchensen/FuXi-CFD-model/blob/main/fuxicfd-model/model/README.md|',
'|FuXi-CFD 缺口|官方权重存在但未作瑞士站全季推理：GRAP/PANG 没有原生 100m，FOUR/GFS 的 0.25° 100m 需构造模型要求的 9×9、1km 风场；作者文档未说明如何从 0.25° 得到 1km 有效输入；官方样本 CPU 一次约 55 秒，强风全量将显著增加运行预算|禁止使用第三方转载；不把仅跑作者样本记作方法(2)站点分数|',
'|MOS、强风阈值|按冻结规则：每站×每源×提前量在 10–12 月 OLS 拟合，1–3 月独立检验；P95 强风、P99 报告不判|22_Lab/05_Projects/Complex_Terrain_Wind_Warning.md「最小示范候选」；阈值不是论文给定|','',
'## 数据来历、失败和下一步','',f"缺失预报对象：{', '.join(m['missing_objects']) or '无'}。分析用四源共同有效的时次，未以另一源替代缺失。",'WindNinja 的直接 griddedInitialization 已以单站/单时次独立试算：最初网格与 DEM 同范围时报 input grids do not completely overlap；给网格加四格边界后成功，CHA 示例与平均初风在站点均为 1.28 m/s（输出已显式 mps）；这只是一次数值敏感性，不是冷季统计。','',"下一步：核逐站风高和地表粗糙度，补 WindNinja 全时次运行以报完整预警误报率；如果 WindNinja 不过、仍要评方法(2)，须先有四源可比的 100m→1km 输入协议、量化预算再试。当前报告绝不外推阵风预报。",'',"数据/代码：stations_frozen.csv、freeze_manifest.json、obs_*.csv、metrics.json、strong_metrics.csv、full_metrics_baselines.csv、mos_coefficients.csv、strong_mae_by_terrain.png、freeze_stations.py、run_forecasts.py、prepare_dem.py、analyze_and_windninja.py。" ]
(P/'results.md').write_text('\n'.join(lines)+'\n')
print(verdict,'tables',len(strong),len(full),'lines',len(lines))
