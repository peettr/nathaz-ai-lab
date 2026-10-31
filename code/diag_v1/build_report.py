"""Build immutable B2 input diagnostic report from executed CSV/JSON artifacts."""
import csv,json,pathlib,collections
P=pathlib.Path(__file__).resolve().parent
inp=list(csv.DictReader(open(P/'input_summary_tsplus.csv')));peaks=list(csv.DictReader(open(P/'peak_summary_5pct.csv')));alle=list(csv.DictReader(open(P/'peak_all_event_5pct.csv')));cat45=json.loads((P/'cat45_paired_5pct.json').read_text());ev=json.loads((P/'eyewall_test.json').read_text());meta=json.loads((P/'meta_5pct.json').read_text());val=json.loads((P/'baseline_validation_5pct.json').read_text());sites=[r['site'] for r in csv.DictReader(open(P/'sites_min.csv'))]
def row(cat,strength,land,var):return next(x for x in inp if x['catalog']==cat and x['intensity']==strength and x['land']==land and x['variable']==var)
def p(x,k):return f"{float(x[k]):.1f}" if x[k] not in ('',None) else '—'
text='''# B2 重启前置诊断 v1：仅目录输入对观测，不触碰设计规范

时间：10-14 23:20 EDT。结论为输入链诊断，不是设计风速的复判或可发表科学结论。原产品与预注册不变。本目录只新增诊断文件；未重算 V50/V700、未调用任何规范站点数值、未上超算。数据与计算来源：RAFT / Xu 等（卡 `NR_xu_2024_raft.md`，PDF 第 3–7 页）[1]；STORM v4 / Bloemendaal 等（卡 `KHFQRECZ_bloemendaal_2020_storm_generation.md`，PDF 第 2、4–5、8 页）[2]；NHC HURDAT2 与 CIRA EBTRK v3.0.2 [3][4]；CLIMADA 6.1.0 固定源码 [5]。

## 口径和可复核性

冻结 19 个站点仅使用 `sites_min.csv` 的站号/经纬度；每个原生轨迹节点到任一站 ≤500 km 入样，北大西洋观测取 1988–2018 同期（EBTRK 有 RMW），状态 TS/HU 且 vmax≥35 kt。HURDAT2 作 vmax/Pc 权威来源；按 NHC 风暴 ID + UTC 6 小时时刻联 EBTRK 的 RMW（海里）与陆地距离。观测 1,515 节点，其中 1,351 匹配 EBTRK、1,305 有正 RMW；EBTRK 的 RMW 由 b-deck/a-deck/旧 EBTRK 混合估计，无统一误差条，且海陆参考岸线与合成目录的 Natural Earth 1:10m 不完全相同[3][4]。`obs_inputs.csv` 含逐点关联与缺失标记。

RAFT 原目录 40,000 条、入 500 km 的有效轨迹 15,063 条；STORM v4 原 107,063 条、入样 32,016 条。输入统计为有效轨迹中 ≥35 kt 原生过程点：RAFT 115,613、STORM 338,599、观测 1,515；原始节点时间间隔分别为 6 h、3 h、6 h，故节点分布会按持续时间加权，不是按独立风暴或模拟年加权。STORM 的 10-min `vmax` 乘原链的假设 1.11 才与 RAFT/HURDAT 1-min kt 分层；此系数未用规范误差校准[1][2]。Pc 为 hPa，ΔP=max(0,1010−Pc) hPa，RMW 单位海里。POCI=1010 hPa 是沿用原链的假设，并非两目录或观测逐时给出；其范围检查仍应按原预注册 1005–1015 hPa。[1][2][5]

### 三方输入分布（仅 TS+；p50 / p90 / p99）

| 目录 | 强度 | 变量 | 有效点 | p50 | p90 | p99 |
|---|---|---|---:|---:|---:|---:|
'''
for cat in ('RAFT','STORM','HURDAT2+EBTRK'):
 for strength in ('ALL','Cat3+'):
  for var,unit in [('vmax_kt','vmax kt'),('pc_hpa','Pc hPa'),('dp1010_hpa','ΔP hPa'),('rmw_nmi','RMW nmi')]:
   r=row(cat,strength,'ALL',var);text+=f"| {cat} | {strength} | {unit} | {r['n']} | {p(r,'p50')} | {p(r,'p90')} | {p(r,'p99')} |\n"
text+='''
全量 TS/Cat1–2/Cat3+ × 海上/陆上（及 ALL）与 p01/p10/p50/p90/p99 在 `input_summary_tsplus.csv`；原始 `input_summary.csv` 包含合成 TD，不与观测 TS+ 主表比较（保留作审计）。Cat3+ 海上/陆上观测 ΔP 的有效点分别 117/8，另 32 点无 EBTRK 海陆标签；陆上小样不作可靠尾部判断。RAFT 的 TS+ vmax p99 低于观测，ΔP p99 也低；Cat3+ RAFT RMW 中位小于观测。作者跨区域验证曾报告登陆 99 分位风偏低约 8 kt、RMW 平均偏小约 19%，只是方向线索，不可当本站点的因果归因（卡 NR_xu_2024_raft.md，PDF 第 6–7 页）[1]。`inputs_comparison.png` 只画独立输入分布，不画设计规范。

## 固定风场链的配对输入替换

对相同合成风暴、同 19 站、同 CLIMADA 6.1.0 H08、15-min 插值、POCI=1010、300-km 风场截断和原 1.07 总换算，分别替换 Pc、RMW、两者，不改其他变量。Pc 替换来自上述同期近岸 HURDAT2 的 1,515 节点二次最小二乘拟合：`Pc(hPa)=1030.4386−0.6978157 V−0.0006672165 V²`（V 为 1-min kt）；拟合范围 35–150 kt，范围外计算用端点裁剪，这是诊断假设而非原论文参数。RAFT 原式 `Pc=1030.222−0.730 V`（Xu 2024 PDF 第 4 页式 2）[1]。把拟合截距称作环境气压是错误的；本链的 POCI 仍单独取 1010。

RMW 替换从同一观测 1,305 正值，按 20-kt 风速箱（±10 kt）×纬度区间 <25/25–35/≥35° 的条件经验分布抽样；池 <20 点则依次扩到全纬度 ±15、±30 kt、最后全体，SHA256(风暴 ID、节点号、固定种子 20261014) 固定抽取。四变体共用每个风暴的同一位置与时序；STORM 亦同样替换作对照。注意：逐节点独立抽取会令 RMW 沿轨非物理跳变，因而 RMW 效应（尤其外围/弱风和 p99）**仅作探索，可能受跳变放大，不能据此冻结修正参数**。这不是作者规定的抽样口径，而是显式诊断假设；合理范围待做事件内相关保持与条件池宽度敏感性。[3][4]

事件选择为 `SHA256(事件编号) mod 20 <1` 的确定性约 5% 样本（RAFT 738、STORM 1,613 条，合计 2,351）。每目录使用同一组被选事件四变体配对；19 站各有同数单场峰值，包括 300 km 截断造成的 0。旧 0.5% 小样结果保留在 `paired_peaks.csv`/`peak_summary.csv`，本报告用扩大样本 `paired_peaks_5pct.csv`/`peak_summary_5pct.csv`；扩大是在发现单站正风样本过少后进行，并非预注册统计检验，p99 仍仅描述。对新增 5% 样本 2,351 个事件×19 站基线对照原封存主链 `evidence_v3/results_v3/*.npz`，44,669 条站点峰值最大绝对差 0.00000334 m/s（`baseline_validation_5pct.json`），故这确实是同一 H08 链，不是近似解析替代。[5]

### 全部站点×事件的峰值分布（含零，m/s）

| 目录 | 变体 | 样本 | 零值占比 | p50 | p90 | p99 |
|---|---|---:|---:|---:|---:|---:|
'''
for cat in ('RAFT','STORM'):
 for v in ('base','Pc_only','RMW_only','both'):
  r=next(x for x in alle if x['catalog']==cat and x['site']=='ALL' and x['variant']==v)
  text+=f"| {cat} | {v} | {r['n']} | {100*float(r['zero_fraction']):.1f}% | {p(r,'p50')} | {p(r,'p90')} | {p(r,'p99')} |\n"
text+='''
因过半数站点×事件无影响，p50 为零；为显示受影响风暴，以下仅把基线峰值 >5 m/s 的相同站点×事件取来计算各变体峰值（m/s）和配对变化百分比。此条件选择不用于任何年重现期估计。

| 目录 | 变体 | 基线>5样本 | 峰值 p50 | p90 | p99 | 配对变化中位 | 原基线最高10%子集变化中位 |
|---|---|---:|---:|---:|---:|---:|---:|
'''
for cat in ('RAFT','STORM'):
 for v in ('base','Pc_only','RMW_only','both'):
  r=next(x for x in peaks if x['catalog']==cat and x['site']=='ALL' and x['variant']==v)
  text+=f"| {cat} | {v} | {r['n_baseline_gt5']} | {p(r,'peak_p50')} | {p(r,'peak_p90')} | {p(r,'peak_p99')} | {p(r,'pct_delta_p50')}% | {p(r,'top10_delta_p50')}% |\n"
text=text.replace('| —% |','| — |')
text+='''
### 逐站受影响单场峰值 p90（m/s；仅基线 >5）

| 站 | RAFT n | RAFT 原/Pc/RMW/双换 | STORM n | STORM 原/Pc/RMW/双换 |
|---|---:|---|---:|---|
'''
for site in sites:
 out=[]
 for cat in ('RAFT','STORM'):
  rr=[next(x for x in peaks if x['catalog']==cat and x['site']==site and x['variant']==v) for v in ('base','Pc_only','RMW_only','both')]
  out.append((rr[0]['n_baseline_gt5'],' / '.join(p(r,'peak_p90') for r in rr)))
 text+=f"| {site} | {out[0][0]} | {out[0][1]} | {out[1][0]} | {out[1][1]} |\n"
text+='''
逐站 p50/p90/p99、配对变化与零值率见 `peak_summary_5pct.csv`、`peak_all_event_5pct.csv`；图 `paired_peak_5pct.png` 标注来源和“不是重现期风速”。RAFT Pc-only 在受影响站点×事件的中位变化很小；RMW-only 对中等风影响大，但 STORM 在同样替换下也有大变化，故不能称 RMW 替换“独自修好 RAFT”。更重要的是替换并未改变目录内 `vmax`、事件数、路径与年代，不能将剩余差异直接归到 AI 或发生率。

## Cat4/5 眼墙假设的直接复核

观测独立静态眼墙检验：同期近站且 EBTRK RMW 有效的 56 个 ≥114 kt 节点，固定纬度、观测 RMW 和 POCI=1010，用 CLIMADA H08 源码中的 B_s 与 Holland 静态径向风公式在 r=RMW 处分别输入观测 Pc 与 RAFT 线性式 Pc；将气压趋势和移速置零作为**静态受控测试**（`eyewall_test.py`，源码 [5] 第 364–435、701–747 行）。RAFT 式相对观测 Pc 的中位偏高 3.62 hPa，静态眼墙风中位损失 2.87%，节点损失的 p10–p90 为 −5.77%～12.83%；不是普遍的 10–15%。

实际完整 H08 链的强风暴测试：在 5% 合成样本中以沿轨最大 vmax≥114 kt 标为 Cat4/5，而不是以站点峰值倒推强度。RAFT 有 70 条此类风暴在 19 站产出 317 条基线>5 的站点×事件；只换观测拟合 Pc，配对峰值中位 +1.84%（p10–p90 −1.53%～+3.80%）。限制为基线>25 m/s 时，39 条风暴/75 条站点×事件为 +2.97%（p10–p90 +1.14%～+4.27%）。RMW-only 在 >5 子集的中位 +15.64%，但基线>25 子集仅 +2.46%，又受逐节点抽样跳变影响；STORM 同样替换后的对照在 `cat45_paired_5pct.json`。因而“线性 Pc 式使 Cat4/5 眼墙风普遍损失 10–15%”在此观测拟合与受控链下不成立；它不能解释整条目录的输入尾部差异。此处正负号均定义为替换后相对原始 H08 的变化，不是对工程标准的偏差。[1][3][4][5]

## 直接用 vmax 的 CLIMADA 6.1.0 实现

固定源码 `climada_windfields_v610.py.txt`（上游 URL [5]）：`MODEL_VANG` 第 55 行；H08 第 205–246 行只有 Pc/ΔP、RMW、纬度、趋势和移速，未读 vmax；H1980 第 158–202、79–95、468–508 行以目录 vmax 扣移速并换算梯度风，然后据它和 ΔP 算 B；H10 第 249–318 行可设 `model_kwargs={'vmax_from_cen': False}`，第 307–308 行调用 `_B_holland_1980`，第 503–508 行该 B 来自目录 vmax 与 ΔP；默认 True 则在第 304–306 行根据 Pc **覆盖**目录 vmax，不能作为“直接用 AI vmax”的候选。转换函数第 1297–1346 行显示 vmax、Pc、RMW 仍均需提供（RMW 输入海里，中心压强不高于环境压强）。H10 非“完全不要 Pc”，但非默认模式确实让目录 vmax 进入剖面；目前仅源码核实与小型 H08 pilot，**没有运行 H10 对观测的资格验证**，不得宣称它会改善结果。[5]

## 参数来源、局限与下一步

| 参数/处理 | 值或规则 | 溯源/性质 |
|---|---|---|
| 观测期、强度 | 1988–2018、TS/HU≥35 kt、距冻结站 ≤500 km | 与 EBTRK 重叠，按源文件同一风暴 ID/UTC；诊断抽样条件[3][4] |
| RAFT Pc、RMW | 原式 hPa、nmi；6 h | Xu 2024 PDF 第 4 页式 2–3；卡 NR_xu_2024_raft.md[1] |
| STORM Pc、RMW、vmax | hPa、km、m/s 10-min；3 h；RMW 除 1.852 | Bloemendaal 2020 PDF 第 2、5、8 页；卡 KHFQRECZ[2] |
| POCI、换算 | 1010 hPa、1.07、STORM vmax×1.11 | 旧 PREREG 假设；不从本站观测或工程标准重新求优 |
| Pc 替换 | 观测二次拟合；35–150 kt 外端点裁剪 | 本轮 1,515 节点的经验诊断；外推/曲线族均是假设 |
| RMW 替换 | 条件经验池与逐节点固定随机数 | 本轮假设；时间不连续，不能作生产性修正 |
| 事件入样 | SHA256(event) mod 20<1 | 5% 描述性样本；无随机重复或置信区间，不能推至 V50/V700 |
| 海陆分档 | 合成 Natural Earth 1:10m land；观测 EBTRK signed land distance | 不同参考海岸线；前者只二值海/陆，不报精确 <10/10–50/>50 km |

**可预注册的修正：现在没有。** 观测条件 Pc 替换仅引起有限强风提升，RMW 效应受时间不连续抽样污染，STORM 同样受它显著影响；更上游的强度尾部与目录路径/频率未通过本次单因素替换分离。下一轮如要探索可先另写 PREREG：①保留原闸 0/闸 1 的门槛与冻结 19 站，不得删站、改阈值；②仅用本轮观测输入检验来预先选择一个直接用 vmax 的模型（候选 H10 `vmax_from_cen=False`）并先验证单位、眼墙/外围表现，Pc 与 RMW 采用明确来源、时间连续的观测条件规则；③锁定后才可在新运行根上重跑目录对比，并把是否改进作为待验证问题。绝不可依据任何规范比对值拟合 Pc、RMW 或选择风场模型。当前 B2 状态继续搁置。

文件：`input_summary_tsplus.csv`（主输入表）、`inputs_comparison.png`、`paired_wide_5pct.csv`、`peak_all_event_5pct.csv`、`peak_summary_5pct.csv`、`cat45_paired_5pct.json`、`paired_peak_5pct.png`、`baseline_validation_5pct.json`、脚本及 `meta_5pct.json`。原始压缩证据 `diag5_output.zip`；诊断不会替代旧产品。Colab CPU 作业完成且会话已 `stop`；账户有其他活跃会话，不能精确归因共享账户的 CU 变化，本任务自身未见 >5 CU 的迹象。
'''
(P/'DIAG_inputs_v1.md').write_text(text)
print('wrote',P/'DIAG_inputs_v1.md',len(text),'characters',len(sites),'sites')
