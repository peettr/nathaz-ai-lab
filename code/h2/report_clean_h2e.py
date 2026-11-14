#!/usr/bin/env python3
"""Render H2 site-cleaned evaluation; outputs are new files only."""
import json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent
D=json.loads((R/'metrics_clean_h2d.json').read_text());m=D['land_metrics'];sea=D['water_platform_metrics'];audit=pd.read_csv(R/'station_clean_h2d.csv');pk=pd.read_csv(R/'peaks_clean_h2d.csv');missing=pd.read_csv(R/'missing_clean_h2d.csv')
regular=D['metadata']['regular_events'];events=regular+['COMBINED','BERYL']
name={'idw':'IDW','ok75':'OK固定','okfit':'OK拟合','era':'ERA5','era_resok75':'ERA5+残差固定','era_resokfit':'ERA5+残差拟合','holland':'H08','holland_resok75':'H08+残差固定','holland_resokfit':'H08+残差拟合'}
def f(x):return '—' if x is None else f'{x:.3f}'
def verdict(x):
 if not x['evaluable']:return '不可评'
 g=x['gain'];frac=x['station_wins']/x['stations']
 return '值得' if g>=.2 and frac>=2/3 else '有条件' if g>=.1 or frac>=2/3 else '插值够用'
L=['# H2 站点清洗后重算（十事件 + Beryl 单列）','',
'2026-10-14；全程 UTC。原 H2/B 节点文件只读，所有结果以 `_clean_h2d`/`_h2d` 为新版本；没有更改冻结 Holland v1 (a) 链系数。十事件合计不含 Beryl。此清洗补充不修改预先判据。', '',
'## 清洗与评分边界','',
'以事件完整候选站表为起点，独立于缺报与评分资格执行空间清洗：规范化 Beryl/Nicholas 的无州前缀 TX 站号；坐标可疑 TX:T89 排除（与 TX:CVB 相同），<2 km 连通近邻每组保留所有事件中有效观测小时数最多者（并列按站号字典序）。剔除站在全部小时的输入、拟合、测试都不存在。水体主类或名称标明离岸平台的站另立池，绝不参与陆地站的 IDW、OK、残差拟合或评价；WorldCover 无返回的站保守排除。`station_clean_h2d.csv` 给每站状态和原因，`near_pairs_h2d.csv` 给距离。', '',
'水体池指“1 km 周边 WorldCover 水体为主或名称显示离岸”，不等于所有站都是真正海上平台：例如 SPG/TPF/EYW 是沿海机场，也按预定水体条件从陆地池分离。该分组不是仪器暴露条件认证。', '',
'持续风只用 IEM METAR sknt、阵风只用 gust；事件登陆前后 12 h，小时最近整点 ±30 min。保留最少 75% 有效小时且 H08 站点模型峰 ±2 h 至少一条有效报告，预测峰与实测峰限同一有观测时刻。未覆盖的真实极值不可验证。', '',
'## 事先判据与结果','',
'在各可评事件（未截尾且≥8站）与十事件合计，最佳背景+残差相对最佳 IDW/固定或拟合 OK：峰值 RMSE 低≥20% 且 ≥2/3 站峰值绝对误差更小为“值得”；10–20% 或仅达其中一项为“有条件”；<10% 为“插值够用”。若“仅满足胜站条件但 RMSE <10%”，仍按原判据列有条件。只在陆地池判定，Beryl 单列。', '',
'|事件|候选陆地站/评分站|最佳插值|最佳融合|峰值 RMSE 基线→融合 (m/s)|降低|胜站|判定|','|---|---:|---|---|---:|---:|---:|---|']
for e in events:
 x=m[e];a=x['methods'][x['baseline']]['peak'];b=x['methods'][x['best_fusion']]['peak']
 # For event use candidate land count, not the original uncleaned event roster.
 n=x['stations']+x['not_eligible']
 L.append(f'|{e}|{n}/{x["stations"]}|{name[x["baseline"]]}|{name[x["best_fusion"]]}|{f(a["rmse"])}→{f(b["rmse"])}|{x["gain"]*100:.2f}%|{x["station_wins"]}/{x["stations"]}|{verdict(x)}|')
L+=['','## 各法并列表','', '峰值 RMSE/bias/MAE 和逐小时 RMSE，单位 m/s。ERA5 不直接同化陆地 10 m 风（审查 2598bcfe 裁决）；本试验的再分析仍非实时预报。',
'|事件|方法|峰值 n|峰值 RMSE|峰值 bias|峰值 MAE|小时 n|小时 RMSE|','|---|---|---:|---:|---:|---:|---:|---:|']
for e in events:
 for key in name:
  v=m[e]['methods'][key];a=v['peak'];h=v['hourly'];L.append(f'|{e}|{name[key]}|{a["n"]}|{f(a["rmse"])}|{f(a["bias"])}|{f(a["mae"])}|{h["n"]}|{f(h["rmse"])}|')
L+=['','## 阵风独立评分与风暴中心距离','', '阵风只与阵风比较，不参与持续风判据。阵风峰值为同一留出站报告小时窗口的最大值。','|事件|阵风方法|n|峰值 RMSE|bias|','|---|---|---:|---:|---:|']
for e in events:
 for key,a in m[e]['methods']['gust'].items():L.append(f'|{e}|{key}|{a["n"]}|{f(a["rmse"])}|{f(a["bias"])}|')
L+=['','|事件|中心距 / RMW|n|最佳插值 RMSE/bias|最佳融合 RMSE/bias|','|---|---|---:|---:|---:|']
for e in events:
 x=m[e]
 for band,group in x['distance_groups'].items():
  a=group[x['baseline']];b=group[x['best_fusion']];L.append(f'|{e}|{band}|{group["n"]}|{f(a["rmse"])}/{f(a["bias"])}|{f(b["rmse"])}/{f(b["bias"])}|')
L+=['','## 水体主类/离岸名称站独立池','',
'独立池不借任何陆地站训练；每事件同时具有效观测的该池站不足 5，故留一后 <4 输入站，无法做同规格 IDW/OK/残差评分；全部不可评，不计入十事件合计。没有把它们的值悄悄扔进陆地池。如下单列候选与缺报覆盖：',
'|事件|水体/平台候选|满足小时覆盖|可留一评分|','|---|---:|---:|---:|']
for e in regular+['BERYL']:
 src=R/f'grid_{e.lower()}_expanded.csv.gz'
 if not src.exists():src=R/f'grid_{e.lower()}_h2.csv.gz'
 ids=pd.read_csv(src,usecols=['station']).station.map(lambda s:s if ':' in s else 'TX:'+s).unique()
 sites=[s for s in ids if audit.set_index('station').loc[s,'status']=='platform']
 x=sea[e];L.append(f'|{e}|{len(sites)}|{len(sites)-x["not_eligible"]}|{x["stations"]}|')
L+=['', '分离站名单：'+', '.join(audit.loc[audit.status=='platform','station'].tolist())+'。若研究真实平台，需要另找同质平台/海上观测网络，不能从本轮站网估算。', '',
'## 剔除及缺报清单','','空间剔除：'+ '; '.join(f'{r.station}（{r.reason}）' for r in audit[audit.status.str.startswith('excluded')].itertuples())+'。',
'WorldCover 无返回（未归陆地/水体）：'+', '.join(audit.loc[audit.status=='unknown_cover','station'].tolist())+'。',
'缺报/截尾见 `missing_clean_h2d.csv`，陆地不评分记录按事件：'+', '.join(f'{e} {m[e]["not_eligible"]}' for e in regular+['BERYL'])+'。', '',
'## 参数来源表','|参数|值/规则|性质|','|---|---|---|',
'|事件/场|B v1 同批十事件+Beryl 附加；B `chain_a_v1.py` 冻结 CLIMADA 6.1.0 H08；最佳路径/b-deck RMW；各缓存 `grid_*`|任务书/B 已有产物；事后路径并非实时预报|',
'|水体与近邻|ESA WorldCover 2021 v200 1 km 圆内主类 80 为水体，或 IEM 站名表明离岸；距离 <2 km 去重；同位 T89 排除|WorldCover/IEM 属性；阈值与优先保留小时数规则是假设，按审查 2598bcfe|',
'|缺报与小时|至少 75% 有效小时且 H08 模型峰 ±2h 有报告；最近整点 ±30min；sknt 0–120kt、gust 0–150kt，gust<sknt 弃|原 H2 假设；不是 IEM 官方 QC|',
'|固定 OK|指数协方差 75 km，归一 nugget .08；IDW 幂次 2|原 H2 假设|',
'|拟合 OK|逐小时、每一留出站训练集分别拟合观测或相应背景残差；25 km 分箱到 300 km，≥4 对/箱，≥3 箱；sill 为训练方差，nugget .08，指数尺度 20–300 km，拟合不足回退 75 km|r2c 参数化假设，非文献常数；目标站完全不进拟合|',
'|H08 时距/阵风|一分钟持续风→METAR ×0.97；海阵风×1.20、陆×1.30|B `PREREG_v1.md` 明确“假设”；参 `ERRATA_v1.md`，非文献给值|',
'|风场/时间|ERA5 10m u/v 插站后取模；H08 按 B 链时间插值；全部 UTC|ARCO ERA5/B 冻结链；已有缓存|', '',
'## 局限','',
'站点缺报在强风中不是随机，真实最大值可能晚于报站停机；留出的是一个站而非整片站群。拟合变差函数使用每个留出站以外的当小时观测，不以留出站选参数；但最终“最佳方法”在评分数据上事后选择，收益带乐观成分。水体主类有沿海机场误判为海上平台的可能，此处按任务规则隔离而不声称仪器在海上。未知地类站保守排除。NHC 事后路径与 b-deck 信息不能视作预报准确度。图与表来源 IEM METAR、Google ARCO ERA5、ESA WorldCover、NHC HURDAT2/ATCF、CLIMADA H08/B v1；新数据仅再次读取 WorldCover 及 IEM 已使用的公开元数据，引用见 `PUBLIC_CITATIONS.md` 已有相应来源。', '',
'脚本 `clean_sites_h2d.py`、`evaluate_clean_h2d.py`、`report_clean_h2e.py`；审计 `station_clean_h2d.csv`、`near_pairs_h2d.csv`；预测 `predictions_clean_h2d.csv.gz`、`peaks_clean_h2d.csv`；图 `peak_scatter_clean_h2e.png`。`results_clean_h2d.md` 中水体池的“满足覆盖”列误写为候选总数，本 e 版已纠正；原文件保留。最初 `station_clean_h2c.csv` 使用未归一的德州站号，已弃用且未覆盖。']
(R/'results_clean_h2e.md').open('x').write('\n'.join(L)+'\n')
land=pk[(pk.pool=='land') & pk.event.isin(regular)]
x=m['COMBINED']['best_fusion'];fig,ax=plt.subplots(figsize=(7,7))
for e,g in land.groupby('event'):ax.scatter(g.obs,g[x],s=21,alpha=.65,label=f'{e} ({len(g)})')
lim=max(land.obs.max(),land[x].max())*1.08;ax.plot([0,lim],[0,lim],'k--');ax.set(xlim=(0,lim),ylim=(0,lim),xlabel='IEM METAR observed peak sustained wind (m/s)',ylabel=f'LOO predicted peak: {x} (m/s)',title='Clean land sites · IEM / ARCO ERA5 / NHC-B v1 H08 / ESA WorldCover');ax.legend(fontsize=7,ncol=2);fig.tight_layout();fig.savefig(R/'peak_scatter_clean_h2e.png',dpi=150)
print('report',len(L),'lines; image sites',len(land),'combined',m['COMBINED']['gain'],m['COMBINED']['station_wins'],flush=True)
