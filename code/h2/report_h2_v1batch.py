#!/usr/bin/env python3
"""Finalize ten frozen-v1 events; Beryl supplementary. No existing result overwritten."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import json,math
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent
src=json.loads((R/'metrics_h2_expanded.json').read_text())
peaks=pd.read_csv(R/'peaks_h2_expanded.csv')
pred=pd.read_csv(R/'predictions_h2_expanded.csv.gz')
missing=pd.read_csv(R/'missing_stations_h2_expanded.csv')
regular=src['metadata']['events'][:-1]
methods=['idw','ok','era','era_resok','holland','holland_resok']
def score(x,y):
 d=np.asarray(x,float)-np.asarray(y,float);d=d[np.isfinite(d)]
 return {'n':len(d),'rmse':float(np.sqrt(np.mean(d*d))) if len(d) else None,'bias':float(d.mean()) if len(d) else None,'mae':float(np.abs(d).mean()) if len(d) else None}
m={e:src['metrics'][e] for e in src['metadata']['events']}
evaluable=[e for e in regular if m[e]['stations']>=8]
pp=peaks[peaks.event.isin(evaluable)];hh=pred[(pred.event.isin(evaluable))&pred.eligible]
by={key:{'peak':score(pp[key],pp.obs),'hourly':score(hh[key],hh.obs)} for key in methods}
by['gust']={key:score(pp[key],pp.obs_gust) for key in ['gust_idw','gust_ok','gust_holland','gust_holland_resok']}
base=min(('idw','ok'),key=lambda k:by[k]['peak']['rmse'])
fusion=min(('era_resok','holland_resok'),key=lambda k:by[k]['peak']['rmse'])
gain=1-by[fusion]['peak']['rmse']/by[base]['peak']['rmse']
wins=int(((pp[fusion]-pp.obs).abs()<(pp[base]-pp.obs).abs()).sum())
groups={}
for label,mask in {'<1R':pp.rmw_ratio<1,'1-3R':(pp.rmw_ratio>=1)&(pp.rmw_ratio<=3),'>3R':pp.rmw_ratio>3}.items():
 groups[label]={'n':int(mask.sum()),base:score(pp.loc[mask,base],pp.loc[mask,'obs']),fusion:score(pp.loc[mask,fusion],pp.loc[mask,'obs'])}
m['COMBINED']={'stations':len(pp),'hourly_records':len(hh),'evaluable':True,'methods':by,'baseline':base,'best_fusion':fusion,'gain':gain,'station_wins':wins,'distance_groups':groups,'not_eligible':int(missing.event.isin(evaluable).sum())}
payload={'metadata':{'regular_v1_events':regular,'additional_event':'BERYL','evaluable_v1_events':evaluable,'combined_excludes_beryl':True,'source':'metrics_h2_expanded.json / peaks_h2_expanded.csv / predictions_h2_expanded.csv.gz','source_combined_row_superseded':True},'metrics':m}
(R/'metrics_h2_v1batch.json').open('x').write(json.dumps(payload,indent=2,ensure_ascii=False))
fig,ax=plt.subplots(figsize=(7,7))
for e,s in pp.groupby('event'):ax.scatter(s.obs,s[fusion],label=f'{e} ({len(s)})',alpha=.6,s=20)
mx=max(pp.obs.max(),pp[fusion].max())*1.1;ax.plot([0,mx],[0,mx],'k--',lw=1);ax.set(xlim=(0,mx),ylim=(0,mx),xlabel='Observed METAR peak sustained wind (m/s)',ylabel=f'{fusion} predicted peak (m/s)',title='IEM METAR / NHC HURDAT2 & ATCF / ARCO ERA5 / CLIMADA H08');ax.legend(fontsize=7,ncol=2);fig.tight_layout();fig.savefig(R/'peak_scatter_h2_v1batch.png',dpi=160)
names={'idw':'IDW','ok':'OK','era':'ERA5','era_resok':'ERA5+残差OK','holland':'v1 H08','holland_resok':'v1 H08+残差OK'}
def fmt(x):return f'{x:.3f}' if x is not None else '—'
def verdict(d):
 if not d['evaluable']:return '不可评'
 g=d['gain'];fraction=d['station_wins']/d['stations']
 return '飓风场景值得做融合' if g>=.2 and fraction>=2/3 else '有条件' if g>=.1 or fraction>=2/3 else '插值够用'
lines=['# H2 v1 同批十事件站点留一（Beryl 附加单列）','',
'2026-10-14；UTC。冻结 B 节点 v1 的 CLIMADA 6.1.0 Holland 2008 + 海陆来流粗糙度、时距因子，原件只读，本目录复制品仅修改相对导入路径（风场函数、常数均未改）。原双事件 `results_h2.md` 保留；`metrics_h2_expanded.json` 的 COMBINED 曾包括 Beryl，此处以新文件纠正为仅十事件，不覆盖旧结果。', '',
'## 事先判据与结论','',
'≥8 有效且未截尾站才按事件判；十个 B v1 事件合并另报，Beryl 附加单列不入合计。峰值 RMSE：最佳背景+残差相对最佳 IDW/OK 降低 ≥20% 且至少 2/3 站峰值绝对误差更低为“值得”；10–20% 或只满足其中一项为“有条件”；<10% 为“插值够用”。峰值为同一留出站有观测时刻的预测最大值与观测最大值；判据没有重订。',
'|事件|合格/候选站|纯插值|融合|峰值 RMSE 基线→融合 (m/s)|降低|改善站|结论|','|---|---:|---|---|---:|---:|---:|---|']
for e in regular+['COMBINED','BERYL']:
 x=m[e];candidate=x['stations']+x['not_eligible'];status=verdict(x)
 if x['evaluable']:
  bb=x['methods'][x['baseline']]['peak']['rmse'];ff=x['methods'][x['best_fusion']]['peak']['rmse']
  lines.append(f'|{e}|{x["stations"]}/{candidate}|{names[x["baseline"]]}|{names[x["best_fusion"]]}|{bb:.3f}→{ff:.3f}|{x["gain"]*100:.2f}%|{x["station_wins"]}/{x["stations"]}|{status}|')
 else:lines.append(f'|{e}|{x["stations"]}/{candidate}|—|—|—|—|—|不可评|')
lines+=['','## 方法对比','', '峰值 RMSE / bias / MAE 与逐小时 RMSE（m/s）；ERA5 陆面站同化口径待核，不可称严格独立留一。','|事件|方法|峰值 n|峰值 RMSE|bias|MAE|小时 n|小时 RMSE|','|---|---|---:|---:|---:|---:|---:|---:|']
for e in regular+['COMBINED','BERYL']:
 for key in methods:
  v=m[e]['methods'][key];a=v['peak'];h=v['hourly'];lines.append(f'|{e}|{names[key]}|{a["n"]}|{fmt(a["rmse"])}|{fmt(a["bias"])}|{fmt(a["mae"])}|{h["n"]}|{fmt(h["rmse"])}|')
lines+=['','## 阵风峰值（独立指标）','','阵风不与平均风混合；H08 阵风因子为预注册假设。','|事件|方法|n|RMSE|bias|MAE|','|---|---|---:|---:|---:|---:|']
for e in regular+['COMBINED','BERYL']:
 for key,a in m[e]['methods']['gust'].items():lines.append(f'|{e}|{key}|{a["n"]}|{fmt(a["rmse"])}|{fmt(a["bias"])}|{fmt(a["mae"])}|')
lines+=['','## 到风暴中心距离分组','','按观测峰值时刻中心距/b-deck RMW，RMSE / bias (m/s)；组内站数极少时不作结论。','|事件|距离组|n|最佳纯插值 RMSE/bias|最佳融合 RMSE/bias|','|---|---|---:|---:|---:|']
for e in regular+['COMBINED','BERYL']:
 for band,g in m[e]['distance_groups'].items():
  a=g[m[e]['baseline']];f=g[m[e]['best_fusion']];lines.append(f'|{e}|{band}|{g["n"]}|{fmt(a["rmse"])}/{fmt(a["bias"])}|{fmt(f["rmse"])}/{fmt(f["bias"])}|')
lines+=['','## 不合格（疑似断报／截尾）站清单','','下表“不合格”是小时数据 <75% 或模型峰时 ±2 h 无持续风报告，不能等同仪器故障；不进入峰值主评分。B v1 分钟级截尾另有独立筛法（模型峰 ±6h ≥648 分钟），两者不混。完整逐站列表在 `missing_stations_h2_expanded.csv`，以下逐站列出。','|事件|站|有效/应有小时|模型峰 UTC|原因|','|---|---|---:|---|---|']
for r in missing.itertuples():lines.append(f'|{r.event}|{r.station}|{r.valid_hours}/{r.expected_hours}|{r.model_peak_utc}|{r.reason}|')
lines+=['','## 参数来源表','|参数|值/规则|来源性质|','|---|---|---|',
'|事件|Delta、Zeta、Ida、Nicholas、Ian、Nicole、Idalia、Debby、Helene、Milton；Beryl 附加；登陆 ±12h UTC|任务书及 B `events_verified.csv`；不含 Francine|',
'|范围/站点|路径任一节点 ≤300 km；事件所在州及邻近州的 IEM ASOS 网络（见脚本 STATES）；档案覆盖日期|任务书 300 km；州域选择为脚本假设；非 HAS1MIN 限定的小时 METAR|',
'|持续/阵风|IEM METAR `sknt` / `gust`，仅持续与持续、阵风与阵风；0.514444 m/s 每 kt|IEM 字段及单位|',
'|小时去重与 QC|最近整点 ±30min 最近报告；sknt 0–120 kt，gust 0–150 kt，gust<sknt 则弃 gust|沿原 H2 假设，并非 IEM 官方 QC|',
'|峰值有效性|有效小时 ≥75%，且 H08 模型峰时 ±2h 内有持续风；不足者“截尾/缺报”，不评分|沿 H2 原假设；不等同 B v1 的分钟级截尾规则|',
'|H08|复制 `chain_a_v1.py`；15min HURDAT2+b-deck RMW/POCI；CLIMADA 6.1.0 Holland 2008；Natural Earth 2/5/10 km 来流投票；陆 z0=.03m、海 z0=.0013m|B `PREREG_v1.md`；500m 中性常通量对数层、单一陆类是“假设”|',
'|时距/阵风系数|1min→METAR 持续 ×0.97；阵风海×1.20/陆×1.30|B `PREREG_v1.md` 明列“假设”，不得当作文献值；署名勘误见 B `ERRATA_v1.md`（Vickery 与 Skerlj 2005，非 Powell）|',
'|ERA5|ARCO 公开 Zarr 10m u/v 双线性站点插值后模长；同化地面站待核|公开再分析；待核独立性|',
'|IDW/OK|IDW 幂次 2；普通克里金指数协方差 exp(-d/75km)、对角 nugget .08；各小时只用其他有效站|沿 H2 假设，未拟合每小时变差函数|',
'|评分/距离|逐站留一，预测峰值与实测峰值取同一可观测时窗；中心距离按观测峰小时 / b-deck RMW|H2 原口径；断报真实峰无法验证|',
'','## 局限与溯源','','B v1 的站点表为距登陆中心 150km 的 HAS1MIN=1 子集，不能直接当本试验 300km 小时报表的同一站网；原始 `station_rows_v1.csv` 的截尾只作旁证。NHC 最佳路径和 b-deck 是事后资料，不是实时预报。靠近风眼站更易断报，分数有幸存者偏差；同机场近邻站未整体留出。ERA5 同化独立性待核。','',
'图来源：IEM METAR、NHC HURDAT2/ATCF b-deck、CLIMADA 6.1.0 H08、Natural Earth 与 Google ARCO-ERA5；图中只画十事件合格站的合计最佳融合。数据引用见本线 `PUBLIC_CITATIONS.md` 已有 H2 条目；本次未引入新外部源。','',
'可复现：`run_h2_expanded.py` + `report_h2_v1batch.py`；事件级 `grid_*_expanded.csv.gz`、`predictions_*_expanded.csv.gz`、汇总 `peaks_h2_expanded.csv`、`metrics_h2_v1batch.json`。旧 `metrics_h2_expanded.json` 中 COMBINED 混入 Beryl，已保留但不用于判据。']
(R/'results_h2_v1batch.md').open('x').write('\n'.join(lines)+'\n')
print('events',evaluable,'combined',len(pp),base,fusion,round(gain*100,2),wins,'missing',len(missing))
