"""Render B2 passage report from immutable event and summary CSVs."""
import csv,pathlib,json,datetime,zoneinfo
P=pathlib.Path(__file__).resolve().parent
coast=list(csv.DictReader(open(P/'passage_coast_categories_v2.csv')));boot=list(csv.DictReader(open(P/'passage_obs_bootstrap_categories_v2.csv')));cond=list(csv.DictReader(open(P/'passage_conditional_v1.csv')));meta=json.loads((P/'passage_meta_v1.json').read_text())
segments=['TX','LA_to_Panhandle','FL_peninsula','Carolinas'];cats=['TS_only','Cat1-2','Cat3+','Cat4-5'];zones=['RMW_le1','RMW_1to3','km_le50','km_le100']
sources=[('RAFT','all','RAFT 12.075'),('RAFT','rate14.5','RAFT 14.5'),('STORM','all','STORM 10000y'),('HURDAT2','1979-2018','OBS 1979–2018'),('HURDAT2','1988-2018','OBS 1988–2018')]
def find(source,period,seg,zone,category):return next(r for r in coast if (r['source'],r['period'],r['segment'],r['zone'],r['category'])==(source,period,seg,zone,category))
def fm(x,n=2):return f'{float(x):.{n}f}'
text=['# B2 近站过境强度×路径×频率收尾（DIAG_passage_v1）',
'时间：'+datetime.datetime.now(zoneinfo.ZoneInfo('America/New_York')).strftime('%m-%d %H:%M EDT')+'。仅比较原始目录输入与 NHC HURDAT2 / CIRA EBTRK；不计算任何站点风场重现期，未调用设计规范。前轮 `DIAG_inputs_v1.md` 与勘误均保持原样。',
'', '## 定义与数据审计',
'19 站及坐标来自 `sites_min.csv`。四段：TX（3站）、LA_to_Panhandle（6站）、FL_peninsula（7站）、Carolinas（3站）；海岸段值是段内站点的等权平均过境次数，不把一场跨站风暴误当作多个独立风暴。每场×每站×每空间环按原生节点筛选 TS/HU≥35 kt，取环内**最大** 1-min vmax 时刻，同时取该节点 Pc 并计算 ΔP=max(0,1010−Pc) hPa；这反映“在该环内达到的最大强度”，不是最近距离时刻强度。每环一场仅计一次；不同站与环可重复。TS_only=35–<64、Cat1-2=64–<96、Cat3+=≥96、Cat4-5=≥114 kt；末档是 Cat3+ 子集，不可四档相加。空间环 RMW_le1 为 d≤RMW，RMW_1to3 为 RMW<d≤3RMW（两者互斥），固定圈 d≤50/100 km 为累积且互相重叠；距离是球面点到站大圆距离，RMW 在原生节点使用海里×1.852。无节点间插值，因此高速过境会漏计；“RMW 不可靠”的固定圈是主归因。',
'RAFT 40,000 条（`RAFT_passage_complete.nc` SHA256 '+meta['source_hashes']['RAFT']+'）；STORM v4 北大西洋 107,063 条，10,000 模拟年（`STORMV4_passage.zip` SHA256 '+meta['source_hashes']['STORM']+'）。RAFT 文件重新完整下载；上一轮留存的 `RAFT.NA.v20231016.nc` 仅 92,012,544 字节，不完整，未参与本轮。两目录有效事件数与各自原始总数一致，观测按此前 `raft_rate_hurdat.py` 同一口径：AL 风暴 ID、至少一次 TS/HU≥35 kt、热带状态首尾历时≥24h，1979–2018 共 483 场（40 年），1988–2018 共 408 场（31 年）。仅热带 TS/HU 节点参与本站过境；非热带化阶段不计。',
'主计量 = 每千条**全部入目录合格风暴**的站点过境场次（与年率无关）：RAFT 分母 40,000、STORM 分母 107,063、观测分母 483/408；“入样”指目录内 TS/生命周期合格的原始风暴而非距站≤500 km 的条件筛选。年值 RAFT 为每千条÷1000×12.075（另列 14.5 敏感性），STORM 实际场次÷10,000 年，观测是当期场次÷40 或 ÷31 年；改变分母定义会改变这些数字。STORM 目录 10-min vmax×1.11 后除 0.514444 转 1-min kt，此 1.11 是既有链假设，并非观测验证换算；RAFT 与 HURDAT2 原生 1-min kt。POCI=1010 hPa 同样是既有假设；Pc 缺测时不补值。来源与页码：Xu 2024 卡 `NR_xu_2024_raft.md` PDF 第 3–7 页；Bloemendaal 2020 卡 `KHFQRECZ_bloemendaal_2020_storm_generation.md` PDF 第 2、4–5、8 页；NHC HURDAT2 [3]、CIRA EBTRK README 第 61–83、157–166 行 [4]。',
'', '## 逐段主表（每千条；四类在每一空间环）',
'每格按 TS_only / Cat1-2 / Cat3+ / Cat4-5 排列；Cat4-5 是 Cat3+ 子集。全体 19 站逐站、五种年率口径见 `passage_station_categories_v2.csv`；主表为段内站点平均。',
'| 空间环 | 海岸段 | RAFT | STORM | OBS 1979–2018 | OBS 1988–2018 |',
'|---|---|---:|---:|---:|---:|']
for zone in zones:
 for seg in segments:
  cells=[]
  for src,per,_ in [sources[0],sources[2],sources[3],sources[4]]:
   cells.append(' / '.join(fm(find(src,per,seg,zone,c)['mean_per_1000'],2) for c in cats))
  text.append('| '+zone+' | '+seg+' | '+' | '.join(cells)+' |')
text+=['','## 年值（场/站/年，含 RAFT 年率敏感性）',
'每格 TS+ / Cat3+；TS+=TS_only+Cat1-2+Cat3+。同站点逐档年值与计数另见 `passage_station_categories_v2.csv`、段均 `passage_coast_categories_v2.csv`。',
'| 空间环 | 海岸段 | RAFT 12.075 | RAFT 14.5 | STORM | OBS 1979–2018 | OBS 1988–2018 |',
'|---|---|---:|---:|---:|---:|---:|']
for zone in zones:
 for seg in segments:
  cells=[]
  for src,per,_ in sources:
   ts=sum(float(find(src,per,seg,zone,c)['mean_per_year']) for c in cats[:3]);maj=float(find(src,per,seg,zone,'Cat3+')['mean_per_year'])
   cells.append(f'{ts:.3f} / {maj:.3f}')
  text.append('| '+zone+' | '+seg+' | '+' | '.join(cells)+' |')
text+=['','## 条件强度与压差（固定 100 km，TS+）',
'值为站点×事件条件样本的 p50 / p90 / p99，单位分别 kt、hPa；同一风暴可能跨站重复，样本数不是独立风暴数。全部空间环、四个阈值及 OBS 两时期在 `passage_conditional_v1.csv`；逐站条件分布见 `passage_station_v1.csv`。',
'| 段 | 数据 | 站点×事件数 | vmax p50/p90/p99 | ΔP p50/p90/p99 |',
'|---|---|---:|---:|---:|']
for seg in segments:
 for src,per,label in [sources[0],sources[2],sources[4]]:
  r=next(x for x in cond if (x['segment'],x['source'],x['period'],x['zone'],x['threshold'])==(seg,src,per,'km_le100','TS'))
  text.append('| '+seg+' | '+label+' | '+r['site_event_n']+' | '+' / '.join(fm(r['v_'+x],1) for x in ['p50','p90','p99'])+' | '+' / '.join(fm(r['dp_'+x],1) for x in ['p50','p90','p99'])+' |')
text+=['','## 小样本与归因边界',
'观测强台风事件很少：固定 100 km、1988–2018 Cat3+ 的段均年率及按观测年份整块 bootstrap（3000 次、种子 20261014）95% 采样区间如下。区间只量化年份抽样，不含观测 RMW、年代代表性、模拟目录率或模型结构误差。',
'| 段 | Cat3+ /站/年 | 年块 95% 区间 | 有事件的年份 /31 |',
'|---|---:|---:|---:|']
for seg in segments:
 r=next(x for x in boot if (x['period'],x['segment'],x['zone'],x['category'])==('1988-2018',seg,'km_le100','Cat3+'))
 text.append(f"| {seg} | {fm(r['mean_per_year'],3)} | [{fm(r['lo95'],3)}, {fm(r['hi95'],3)}] | {r['nonzero_years']}/31 |")
text+=['观测 EBTRK RMW 在 1988–2018 才有可比支持；1979–2018 的 RMW 圈计数实际上前 9 年缺测，表中仅作**不可比下界**，不能解释为真实 40 年 RMW 频率。即使在 1988–2018 年，EBTRK RMW 未必每个近站节点可用；近 300 km 的 19 站×节点累计匹配 2109 / 3297（约 64%，跨站重复），且缺测并非随机。RMW 圈与固定圈不能直接互相当成一致性验证；RAFT RMW 为经验式，STORM 为目录参数，EBTRK 是混合来源估计。',
'固定 100 km 的 19 站等权均值：RAFT TS+ 0.168、Cat3+ 0.0104 场/站/年；STORM 0.133、0.0212；OBS 1988–2018 0.321、0.0374（1979–2018 为 0.315、0.0382）。RAFT 相对 STORM 的 TS+ 并未偏少（+27%），但强风比例 Cat3+/TS+ 为 6.2% 对 16.0%；相对观测 TS+ 约 52% 且 Cat3+ 约 28%，观测条件强台风比例 11.6%。RAFT 14.5 年率时 100 km TS+ 0.202、Cat3+ 0.0125，强风比例不变，仍明显小于同期观测强风率。四段条件强度表显示，RAFT 在 TX/LA-Panhandle/Carolinas 的 TS+ vmax p90 与 ΔP p90 均比 STORM 低，FL peninsula 差距较小；Pc 是由 vmax 经验式导出的，不能把这两个尾部差异当独立原因。',
'判读：相对 STORM，RAFT 的近站 TS+ **次数不低**，其 Cat3+ 场次低主要随环内强度分布偏弱；相对 HURDAT2，RAFT 的近站 TS+ 频率与 Cat3+/TS+ 比例都低，故按本任务面向观测的四择一是 (iii) 两者都有。这里的“频率”是原生节点落入站点固定圈的目录联合结果，既包含路径又包含总体事件率，无法再将二者独立识别；最近节点漏计、风速时均换算、年代差异、EBTRK 缺测及观测年样本小，限制因果归因。**不得**从输入诊断反推任何工程风速偏差的百分比，也不据此宣布新风场链有效。',
'图 `passage_v1.png` 左为固定 100 km Cat3+ 年率，右为同圈条件 vmax p90；图注注明原始数据，非站点模型风。审计：`passage_events_v1.csv` 是每事件×站×环一行，`passage_meta_v1.json` 含原目录计数/散列/RMW 覆盖；`passage_station_v1.csv` 为累积阈值及各站 p50/p90/p99；分类主表采用新增的互斥 `*_categories_v2.csv`，没有覆盖最初累积阈值表。脚本 `passage_v1.py`、`passage_conditional_v1.py`、`passage_categories_v2.py` 可复现。全程 工作站 本地、0 SU、未启用 Colab。',
'', '## 来源',
'[1] Xu 等 2024 RAFT：`16_PETW/05_Literature_Wiki/wiki/designload_step5/papers/NR_xu_2024_raft.md`，PDF 第 3–7 页；https://www.nature.com/articles/s41597-024-02952-7.pdf',
'[2] Bloemendaal 等 2020 STORM：`16_PETW/05_Literature_Wiki/wiki/designload_step5/papers/KHFQRECZ_bloemendaal_2020_storm_generation.md`，PDF 第 2、4–5、8 页；公开 v4 https://data.4tu.nl/articles/dataset/STORM_IBTrACS_present_climate_synthetic_tropical_cyclone_tracks/12706085/4',
'[3] NHC HURDAT2 Atlantic，https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt；年率算法 `../raft_rate_hurdat.py`。',
'[4] CIRA EBTRK v3，`EBTRK_README.txt` 第 61–83、157–166 行，https://rammb2.cira.colostate.edu/wp-content/uploads/2020/11/EBTRK_README_v3.0.2_16-Oct-2022.txt',
'', '## 结论',
'相对观测，RAFT 近站强风暴偏少是 (iii) 过境频率和过境强度两者都有：固定 100 km 内 19 站均值 TS+ 为 0.168 对观测 0.321 场/站/年，Cat3+ 为 0.0104 对 0.0374；Cat3+ 在近站 TS+ 中的比例为 6.2% 对 11.6%。相对 STORM，RAFT 的 TS+ 并不偏少（0.168 对 0.133），主要差在过境强度（Cat3+ 比例 6.2% 对 16.0%）。年块观测尾部区间宽，本诊断不足以授权据此选择新模型或宣布工程判闸结果。']
path=P/'DIAG_passage_v1.md';path.write_text('\n'.join(text)+'\n');print(path,len(text))
