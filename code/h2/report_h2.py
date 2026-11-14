#!/usr/bin/env python3
"""Generate H2 report from on-disk verified metrics, not manually transcribed figures."""
import json,csv
from pathlib import Path
R=Path(__file__).resolve().parent
m=json.loads((R/'metrics_h2.json').read_text());missing=list(csv.DictReader((R/'missing_stations_h2.csv').open()))
method_names={'idw':'IDW','ok':'OK','era':'ERA5','era_resok':'ERA5+残差OK','holland':'H08 Holland','holland_resok':'H08 Holland+残差OK'}
lines=['# H2 登陆飓风小时 METAR 站点留一重建','',
'口径：BERYL 2024、NICHOLAS 2021，NHC 登陆 ±12 h，全部日期与时刻为 UTC。输入为 Iowa Environmental Mesonet（IEM）的逐小时 METAR 2-min 平均持续风（sknt）；gust 单列，只与 gust 比。Holland 用 B 节点冻结的 CLIMADA v6.1.0 H08＋Natural Earth 来流海陆分类＋0.97 的约 2-min 因子，不重新拟合模型系数；ERA5 为 ARCO-ERA5 10 m U/V 模长。','',
'来源：NHC HURDAT2、ATCF b-deck、IEM TX_ASOS／小时 METAR、Google Research ARCO-ERA5、CLIMADA v6.1.0、Natural Earth；详细版本与链接见 `22_Lab/PUBLIC_CITATIONS.md` 的 H2 条目，以及本目录 `iem_urls_*_h2.json`。B 节点原件只读。图标题标注来源。','',
'## 事先判据与结论','',
'以每站事件最大观测小时持续风的 RMSE 为主；方法预测在该站有观测的相同小时上的最大值，与观测最大值对照。最好的背景＋残差比 IDW/OK 中较好者 RMSE 至少降低 20% 且至少 2/3 站的峰值绝对误差减小，才判“飓风场景值得做融合”；10–20% 或只满足其一为“有条件”；<10% 为“插值够用”。本试验所得均按此判据，不因结果调整阈值。','']
for e,x in m.items():
 gain=x['gain']*100;wins=x['station_wins'];n=x['stations'];b=x['methods'][x['baseline']]['peak']['rmse'];f=x['methods'][x['best_fusion']]['peak']['rmse']
 verdict='飓风场景值得做融合' if gain>=20 and wins/n>=2/3 else '有条件' if gain>=10 or (gain>=20 or wins/n>=2/3) else '插值够用'
 lines.append(f'{e}: 合格 {n} 站、未合格 {x["not_eligible"]} 站；{method_names[x["baseline"]]} {b:.3f} → {method_names[x["best_fusion"]]} {f:.3f} m/s，降低 {gain:.2f}%，逐站改善 {wins}/{n}（{wins/n*100:.1f}%）；{verdict}。')
lines+=['','## 方法对照','', '峰值和逐小时列均为 RMSE / bias / MAE，单位 m/s；峰值样本数按站，逐小时样本数按观测到的小时。','', '|事件|方法|峰值站数|峰值 RMSE|峰值 bias|峰值 MAE|小时样本数|小时 RMSE|小时 bias|小时 MAE|','|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for e,x in m.items():
 for method,name in method_names.items():
  a=x['methods'][method]['peak'];h=x['methods'][method]['hourly'];lines.append(f'|{e}|{name}|{a["n"]}|{a["rmse"]:.3f}|{a["bias"]:+.3f}|{a["mae"]:.3f}|{h["n"]}|{h["rmse"]:.3f}|{h["bias"]:+.3f}|{h["mae"]:.3f}|')
lines+=['','峰值误差是预测峰值减实测峰值。ERA5 的站点同化口径仍待核，ERA5+残差的留一不能称完全无站点信息。Holland 本身未用当前验证站的 METAR 调参，但 NHC 后验最佳路径、强度和 b-deck 是事后资料，非实时预报；结果不得外推为未来预报技能。','',
'## 阵风峰值（独立评分）','', 'ERA5 10 m 平均风不直接转换为阵风；此处仅列 IDW、OK、Holland及其残差法。H08 的阵风因子是 B 节点冻结假设，不是阵风观测拟合值。','', '|事件|方法|n|RMSE|bias|MAE|','|---|---|---:|---:|---:|---:|']
for e,x in m.items():
 for k,v in x['methods']['gust'].items():
  lines.append(f'|{e}|{k}|{v["n"]}|{v["rmse"]:.3f}|{v["bias"]:+.3f}|{v["mae"]:.3f}|')
lines+=['','## 离中心／RMW 分组','', '分组按留出站实测持续风峰值对应小时，到 NHC 中心的距离除该小时线性插值 b-deck RMW。两列为各事件最佳纯插值和最佳融合的峰值 RMSE / bias (m/s)；样本很小者只描述，不作结论。','', '|事件|距离/RMW|站数|基线 RMSE / bias|融合 RMSE / bias|','|---|---|---:|---:|---:|']
for e,x in m.items():
 for band,g in x['distance_groups'].items():
  bb=g[x['baseline']];ff=g[x['best_fusion']];lines.append(f'|{e}|{band}|{g["n"]}|{bb["rmse"]:.3f} / {bb["bias"]:+.3f}|{ff["rmse"]:.3f} / {ff["bias"]:+.3f}|')
lines+=['','## 缺测／断报站','', '入选站点是 TX_ASOS 档案覆盖事件且距 ±12h 路径任一节点 ≤300 km；“不合格”不等于断报确诊，包括档案虽覆盖但逐时报表缺少、METAR 数值 QC、时窗内 <18/24 个持续风小时，或冻结 H08 预测本站峰时 ±2h 无持续风报告。为避免缺报隐去峰值，不合格站均不参与上述主评分；下表逐站明细。','', '|事件|站|有效 / 预期小时|H08 本站模型峰 (UTC)|峰时附近有报|','|---|---|---:|---|---|']
for r in sorted(missing,key=lambda x:(x['event'],x['station'])):lines.append(f'|{r["event"]}|{r["station"]}|{r["valid_hours"]}/{r["expected_hours"]}|{r["model_peak_utc"]}|{r["near_model_peak"]}|')
lines+=['','## 参数来源表','', '|参数|取值／规则|来源性质与理由|','|---|---|---|',
'|事件与时窗|Beryl 2024 / Nicholas 2021，NHC 登陆 ±12 h，小时对齐 UTC|任务书预设；HURDAT2 登陆时刻来自只读 B 节点|',
'|站网|TX_ASOS，档案日期覆盖，距事件窗口 NHC 路径任一点 ≤300 km|任务书预设；没有强制 HAS1MIN，因本次小时 METAR|',
'|平均风与阵风|IEM `sknt`、`gust` knot ×0.514444 m/s|IEM 字段；2-min 平均风只对持续风，不用 gust 代替，转换物理常数|',
'|逐小时去重|METAR 时间戳向最近整点舍入，取距离整点最近报告；`report_type=3,4`|沿用 H r1 脚本规则；同一小时只留一条报告|',
'|数值 QC|sknt 0–120 kt，gust 0–150 kt；同条 gust<sknt 则该 gust 排除|假设：宽上限只删明显畸值，不是 NCEI 的官方 QC 阈值|',
'|断报门槛|24h 至少 18 有效持续风小时，且 H08 模型峰时 ±2h 至少一条|假设：避免明显截尾的峰值；门槛受模型峰时误差影响；无报站不计 0|',
'|H08 风场|B 节点原 `chain_a_v1.py` 的 CLIMADA v6.1.0 H08 风场函数、15min 最佳路径+b-deck 插值、Natural Earth 2/5/10km 来流海陆分类|源自 B 冻结代码 `PREREG_v1.md`；本站不调 0.97、陆海/阵风系数；B 预注册说明其经验假设与局限|',
'|ERA5|ARCO 公开 Zarr，10 m U/V 插到站点、逐小时模长|H r1 背景读取代码；站点同化是否独立待核|',
'|IDW|反距离平方、同一小时可用站，不含留出站|假设；沿用 H r1 固定幂次 2|',
'|普通克里金|每小时固定指数协方差 exp(−d/75km)，对角 nugget 0.08，常值未知均值|假设；沿用 H r1 固定版。未拟合事件经验变差函数；同一权重用于持续风及其背景残差|',
'|峰值比较|每站事件有观测小时上的预测最大 vs 该时段观测最大；逐小时仅该站有效观测小时|假设：保障共同可观测窗口；未验证真正因断报而缺失的事件峰|',
'|分组|留出站实测峰时到 NHC 中心 / 同时刻 b-deck RMW|任务书预设；RMW 线性插值沿用 B 代码|',
'','## 已知局限','',
'1. 双事件、德州机场周围的合格站偏样本；缺测并非随机，重灾区断报站的真实峰值可能更高。不能把“有条件”当成已证明的登陆核心区风场重建能力。',
'2. 逐小时 METAR（一个站每小时一条）会漏掉两次报之间的分钟级极值；事件峰的时距是窗口内“最大小时平均风”，并非真实 1-min 峰、也不是阵风。',
'3. B 的风场是后验最佳路径与海陆简化暴露，不是实时预报；ERA5 亦是后验再分析且是否包含被留站信息待核。',
'4. 固定变差函数未按小时拟合；同小时残差可含邻站局部极值，Holland+残差逐小时 RMSE 比 ERA5+残差更差，峰值收益不可误解为全时段都占优。',
'5. 风暴中心距离分组以观测峰时定义，不代表峰时恰为 NHC 登陆，也未含其他州站；唯一站点留一可让同机场/近邻站仍在训练侧，尚未做按机场群分组隔离。',
'','## 可复现文件','',
'`run_h2.py` 一次完成下载、B 风场、LOO、JSON、图；`report_h2.py` 由 JSON 生成本报告。`grid_*_h2.csv.gz` 含背景、观测和距离；`predictions_h2.csv.gz` 含逐小时逐站预测；`peaks_h2.csv` 是峰值评分原表；`missing_stations_h2.csv` 是逐站断报候选。图 `peak_scatter_h2.png` 来源 IEM／NHC HURDAT2／ATCF／ARCO-ERA5／CLIMADA H08。']
(R/'results_h2.md').write_text('\n'.join(lines)+'\n')
print('wrote',R/'results_h2.md', 'missing',len(missing))
