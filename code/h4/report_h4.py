import json
from pathlib import Path
import pandas as pd
R=Path(__file__).resolve().parent;p=json.loads((R/'metrics_h4v3.json').read_text());m=p['metrics'];st=p['status'];dates=p['selected'];cand=pd.read_csv(R/'candidate_dates_h4.csv').set_index('utc');meta=pd.read_csv(R/'station_clean_h4.csv');metar=pd.read_csv(R/'metar_crosscheck_h4.csv.gz');peak=pd.read_csv(R/'peaks_h4v3.csv')
lines=['# H4 达拉斯雷暴大风：一分钟站点留一小试','','本文件仅使用 `metrics_h4v3.json` 作为有效指标：初版 `metrics_h4.json`/v2 的站距误记为全站最近距及首个可评分钟站距，原文件保留但距离栏作废；v3 改为各站所有可评分钟到当分钟有风观测的最近输入站距离中位数，峰值预测数字不变。五个候选日有四日满足≥8个有效陆地站；2025-03-04 不可评。事先判据见 `prereg_h4.md`，时间 UTC。','','## 事件筛选与观测','','NOAA 2020–2025 Storm Events details：德州、31.5–34°N / 95.5–98.5°W、事件类型 Thunderstorm Wind，按 UTC 日计数；优先任务书点名两日，再按报告数降序取三个日子。仅代表有报告的雷暴大风，不代表下击暴流真值。窗口以该日附近区域内 IEM 1 分钟阵风最大值时刻 ±3 h；该最大值可能来自最终留出站，窗口定义并非完全无留出信息。小时 METAR 另下载核对是否有报告，不和分钟主分数混合。','','|UTC 日|NOAA 区内报告|区域分钟阵风峰时 UTC|窗口内有分钟数据站/候选|≥75% 连续风与阵风站|小时 METAR 行/站|评分|','|---|---:|---|---:|---:|---:|---|']
for d in dates:
    w=json.loads((R/f'window_{d.replace("-", "")}_h4.json').read_text());z=st[d];h=metar[metar.event==d];lines.append(f"|{d}|{int(cand.loc[d,'reports'])}|{w['regional_gust_peak_utc']}|{w['observed_stations']}/{z['land_candidate']}|{z['eligible_both']}|{len(h)}/{h.station.nunique()}|{'可评' if m[d]['evaluable'] else '不可评（仅5站）'}|")
lines+=['','## 峰值与逐分钟结果（m/s）','','每种方法独立取该事件同一有效分钟的预测峰，与同一批有效分钟观测峰比较。负偏差表示低估。最优纯插值从 IDW/固定 OK/拟合 OK 中取；最优 ERA5 融合从固定/拟合残差 OK 中取。逐分钟 RMSE 不是峰值 RMSE。','', '|事件|站数|最佳纯插值|最佳融合|峰值 RMSE 插值→融合|降幅|改善站|峰值 bias 插值→融合|逐分钟 RMSE 插值→融合|判定|','|---|---:|---|---|---:|---:|---:|---:|---:|---|']
for d in dates+['COMBINED']:
    z=m[d]
    if not z['evaluable']:
        lines.append(f"|{d}|{z['n']}|—|—|—|—|—|—|—|不可评|");continue
    b=z['baseline'];f=z['best_fusion'];bp=z['methods'][b]['peak'];fp=z['methods'][f]['peak'];bh=z['methods'][b]['minute'];fh=z['methods'][f]['minute']
    lines.append(f"|{d}|{z['n']}|{b}|{f}|{bp['rmse']:.3f}→{fp['rmse']:.3f}|{z['gain']*100:.2f}%|{z['wins']}/{z['n']}|{bp['bias']:.3f}→{fp['bias']:.3f}|{bh['rmse']:.3f}→{fh['rmse']:.3f}|{z['verdict']}|")
lines+=['','|事件|方法|峰值 n|RMSE|bias|MAE|逐分钟 n|RMSE|','|---|---|---:|---:|---:|---:|---:|---:|']
for d in dates+['COMBINED']:
    if not m[d]['evaluable']:continue
    for meth,a in m[d]['methods'].items():
        x=a['peak'];y=a['minute'];lines.append(f"|{d}|{meth}|{x['n']}|{x['rmse']:.3f}|{x['bias']:.3f}|{x['mae']:.3f}|{y['n']}|{y['rmse']:.3f}|")
lines+=['','## 阵风、站距与孤立峰','','一分钟 gust_sknt 为独立 5 秒阵风量；ERA5 10m U/V 是持续风背景，没有相同定义的阵风背景。故阵风只能报 IDW/OK 阵风对阵风，不对“ERA5 阵风融合”套主判据；这项是预设对比未能执行的缺口。孤立峰定义为本站事件内观测持续风峰值高出同事件其他所有可评站峰值至少 5 m/s，不等同同一分钟孤立峰或下击暴流证据。','','|事件|阵风峰值 RMSE IDW/OK75/OKfit|阵风最佳插值 bias|孤立峰 n|','|---|---|---:|---:|']
for d in dates+['COMBINED']:
    if not m[d]['evaluable']:continue
    z=m[d];gm=min(z['gust_peak'],key=lambda x:z['gust_peak'][x]['rmse']);lines.append(f"|{d}|{' / '.join(f'{z['gust_peak'][x]['rmse']:.3f}' for x in ['gust_idw','gust_ok75','gust_okfit'])}|{z['gust_peak'][gm]['bias']:.3f}|{z['isolated_peak_count']}|")
lines+=['','|事件|距最近有观测输入站中位距离组|站数|纯插值峰值 RMSE|融合峰值 RMSE|','|---|---|---:|---:|---:|']
for d in dates+['COMBINED']:
    if not m[d]['evaluable']:continue
    for x in m[d]['distances']:
            if x['n']:lines.append(f"|{d}|{x['bin']} km|{x['n']}|{x['baseline']['rmse']:.3f}|{x['fusion']['rmse']:.3f}|")
            else:lines.append(f"|{d}|{x['bin']} km|0|—|—|")
lines+=['','## 清洗和参数来源','','ASOS1MIN 网络在目标框共14站。H2/H3 的站点清洗规则重新应用：WorldCover 2021 v200 站点周边1 km主类，水体或平台另池，未知类保守不入，T89 坐标疑点排除，<2 km 连通对保留五事件累计有效分钟最多者。本次14站均为陆地、未发现<2 km站对，详细见 `station_clean_h4.csv`。每事件低于75%双变量覆盖的站不评分，但它已有的分钟值仍可当别站输入；无资料者不参与任何拟合。','','|参数|来源/性质|','|---|---|','|雷暴事件及 UTC 报告|NOAA NCEI Storm Events details，`events_h4.json` 精确版本 URL；Texas 按 America/Chicago 时区换 UTC；研究区框和挑选规则来自任务书/本轮预登记|','|分钟持续风 sknt、5秒阵风 gust_sknt|IEM ASOS 1-minute，逐事件 URL 文件；kt×0.514444 m/s；不与小时 METAR 混合|','|小时 METAR|IEM ASOS archived METAR，仅报告覆盖对照，逐日下载 URL 文件；不是主评分|','|ERA5 10m 风|Google Research ARCO ERA5 公共 Zarr，小时 10m u/v 双线性空间插值后线性时间插值至分钟，再求风速；再分析不是独立预报，站点同化情况待核|','|WorldCover|ESA WorldCover 2021 v200 via Microsoft Planetary Computer 1km 主类，或复用 H2/H3 已有同站类别|','|IDW/OK|假设：IDW 幂2；OK 指数协方差75 km、nugget .08；拟合：训练站小时风中位数经验变差函数25 km箱、20–300 km拟合，样本稀缺时回退75 km。逐分钟留一目标站不参与拟合|','|覆盖及 QC|假设：361个分钟至少271分钟同时有有效持续风和阵风；≥4个其他同分钟站才预测；持续风0–120 kt、阵风0–150 kt，阵风≥持续风。详细断报见 metrics_h4v3.json|','|HRRR f01|未下载/未评分；上游分析已同化站点，即便f01也不作独立留一证据|','','限制：只有14个具1分钟档案站、四个可评事件共44站事件；2025-03-04 虽有87条 Storm Events 报告，但区域一分钟档案只有5站满足覆盖要求，不能凭小时 METAR 填补分钟峰。雷暴尺度峰位可在站间移动，站点峰不是连续场真值。事件窗口由全站观测定，事件/方法择优会乐观，阵风融合比较缺失；小时 vs 分钟支持集不同，不能套用 H2/H3 数字。此处孤立峰计数为零仅是“高出所有其他站峰值”的严格定义下的结果，不证明没有局地极值。','','数据源：NOAA NCEI https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/ ；IEM https://mesonet.agron.iastate.edu/request/asos/1min.phtml 及 https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?help= ；ARCO ERA5 https://github.com/google-research/arco-era5 ；ESA WorldCover https://doi.org/10.5281/zenodo.7254221 。新源均已在 PUBLIC_CITATIONS.md 的既有条目中，未越出 h4 写入范围。','','## 结论','','四个可评事件合计，持续风事件峰值最佳纯插值 IDW 4.776 m/s，ERA5+固定残差 OK 4.786 m/s（恶化0.19%），26/44站绝对误差改善；峰值 bias −3.245→−3.330 m/s。按开算前判据为“插值够用”。纯插值阵风峰值最佳 OK75 RMSE 6.848 m/s、bias −5.079 m/s；ERA5 阵风融合未能同量比较，不能称“阵风融合插值够用”。']
(R/'results_h4.md').write_text('\n'.join(lines)+'\n');print('wrote',len(lines),'lines', 'events',p['evaluated'])
