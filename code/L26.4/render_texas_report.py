"""Render small Colab JSON summaries; no model computation on 工作站."""
import json,pathlib,datetime,hashlib
B=pathlib.Path(__file__).resolve().parent
S=json.loads((B/'colab03/texas_metrics.json').read_text())
A=json.loads((B/'colab03/texas_air_metrics.json').read_text())
W=json.loads((B/'colab03/west_intervention.json').read_text())
C=json.loads((B/'colab03/west_comparison_corrected.json').read_text())
M=json.loads((B/'colab03/window.json').read_text())
assert A['n']==10 and W['n']==3 and list(S['groups'])==['strict','overlap']
assert sum(S['groups'][g]['grid_cells'] for g in S['groups'])==440*408
assert all(len(S['groups'][g]['rmse'][m][v])==72 for g in S['groups'] for m in ('aero','persistence') for v in ('mslp','u10','v10','t2m','speed'))
assert all(len(A['groups'][g]['rmse'][m][v])==72 for g in A['groups'] for m in ('aero_air','neuralgcm','persistence') for v in A['variables'])
intro='''偏离已批方案，待 Liang Hu 确认：原判据②的「纯 NeuralGCM 近地面」不存在。按 Lead 决策 `04_Decisions/L26.4_判据②对照b近地面不可用_20261022.md`，近地面标不可用并保留持续性，高空 10 项另给纯 NeuralGCM 对照；原判据不能直接宣称已过。

# L26.4-07 德州零样本：受控 A100 结果（10-22）

数据来源：NOAA 公开 HRRR 分析 f00（`noaa-hrrr-bdp-pds`，Surface 2024-04 全月逐小时；高空 wrfprs 2024-04-01 00Z—04-13 00Z 的逐小时）、作者 HF AERO-ODE 西部权重及 ERA5 全球初值（仓库 commit 99516ae9cf）。模型权重/归一化统计量冻结，未微调。2024-04-01—10 每天 00Z，10 个起报，逐次 72 h；逐格在 HRRR Lambert 原网格 (y=0, x=810) 截 440×408，所有数字脚本生成。

## 窗口与静态场
'''
lines=[intro]
lines.append('四角（按数组先行后列，纬度/经度 °）：'+ '；'.join(f'{lat:.4f}, {lon:.4f}' for lat,lon in M['corners'])+'。\n')
lines.append(f"西部训练域重叠 {S['groups']['overlap']['grid_cells']} 格（{M['overlap_fraction']*100:.3f}%），严格训练域外 {S['groups']['strict']['grid_cells']} 格（{M['strict_fraction']*100:.3f}%）；按 HRRR 原网格相同索引矩形计算。\n")
lines.append('AIR 5 通道及 Surface 14 通道的静态输入由 HRRR HGT:surface、VGTYP:surface 重建；地形和土地类数据源与作者 MODIS/DEM 未给版本并不等同，属假设。粗糙度 z0 用论文 Table 4（物理 PDF 第 15 页）IGBP 0–17 查表，`Norm(log z0)`；HRRR VGTYP 17（水体）映射 Table 4 的 0（水体），其余类号原样保留；坡向不用 z-score、方向与作者西部文件一致。\n')
lines.append('| 西部逐通道 | 相关系数 r | 最大绝对差 |\n|---|---:|---:|')
for k,v in C.items():lines.append(f"| {k} | {v['corr']:.4f} | {v['max_abs_diff']:.3f} |")
lines.append('地类掩膜与 z0 通道对不上作者文件，尤其 forest 与 z0；不能宣称静态场完全等价。来源：`colab03/west_comparison_corrected.json`。\n')
lines.append('西部区分检验：04-01 至 04-03 相同起报、权重与归一化，作者原静态 vs 全通道重建静态。每组 RMSE = sqrt(Σ(预报−HRRR)²/格点·时次数)，相对差 = |RMSE重建−RMSE原|/RMSE原；两者只改静态输入。\n')
lines.append('|变量|原静态 RMSE|重建静态 RMSE|相对差 %|\n|---|---:|---:|---:|')
for r in W['rows']:lines.append(f"|{r['variable']}|{r['original_rmse']:.4f}|{r['reconstructed_rmse']:.4f}|{r['relative_difference']*100:.3f}|")
lines.append('这项仅界定该配置下整组静态替换的 RMSE 变化，不能单独归因给 z0 或地类；德州指标须带此静态来源局限阅读。来源：`colab03/west_intervention.json`。\n')
lines.append('## 近地面：严格零样本（主结果）与重叠格点（参考）\n')
lines.append('72 个时效完整值见 `colab03/texas_metrics.json`；下表为程序从该文件取 1/24/48/72 h 的切片。RMSE = sqrt(Σ(预测−HRRR)²/N)，N=10 个起报×该组格点数；风速 = hypot(U10,V10)。持续性使用每次起报 00Z 的 HRRR f00 固定至所有时效。纯 NeuralGCM 对 MSLP、U10、V10、10 m 风速、T2m 均不可用：该模型只输出 35 个等压面通道，这些近地面量来自 Surface 诊断网络（`AERO_ODE_v3.py:125–138`、`test_film_00z_RMSE.py:231–245`）；不得用等压面冒充。\n')
for g,label in [('strict','严格训练域外'),('overlap','西部重叠')]:
 block=S['groups'][g];lines.append(f'### {label}：{block["grid_cells"]} 格\n')
 lines.append('|变量|方法|1 h|24 h|48 h|72 h|\n|---|---|---:|---:|---:|---:|')
 for var in ('mslp','u10','v10','t2m','speed'):
  for method in ('aero','persistence'):
   vals=block['rmse'][method][var]
   lines.append(f"|{var}|{method}|"+'|'.join(f'{vals[i-1]:.3f}' for i in (1,24,48,72))+'|')
 lines.append(f"该组 72 h 逐时每时效样本 N={block['count_per_lead'][0]} 格点·起报；MSLP 单位 Pa、U/V/风速 m/s、T2m K。\n")
lines.append('## 强风事件与 Top-k\n')
lines.append(f"强风阈值 = 本窗口 2024-04 全月逐小时 HRRR f00 风速 P95 = {S['p95_full_april_mps']:.4f} m/s（总体 {S['p95_population']} 格点·时次）。强风 RMSE=sqrt(Σ(预报风速−观测风速)²/N95)，偏差=Σ(预报−观测)/N95。Top-k 各组独立取十次起报的 1–72 h 所有格点·时次，k=ceil(0.01N)，捕获率=预报前 k 与观测前 k 的交集/k；等值时按时间和格点序选先出现者。\n")
lines.append('|组|方法|强风 N|风速 RMSE m/s|偏差 m/s|Top-k k/N|捕获率 %|\n|---|---|---:|---:|---:|---:|')
for g in ('strict','overlap'):
 for method in ('aero','persistence'):
  strong=S['groups'][g]['strong'][method];top=S['groups'][g]['topk'][method]
  lines.append(f"|{g}|{method}|{strong['n']}|{strong['speed_rmse']:.3f}|{strong['speed_bias']:+.3f}|{top['k']}/{top['n_scored']}|{top['capture_rate']*100:.3f}|")
lines.append('模型为确定性预报，覆盖率检验不适用；这组 2024 年 4 月样本无台风案例。\n')
lines.append('## 高空 10 项：NeuralGCM 真正可用的两条对照\n')
lines.append('NeuralGCM 标准预测（不是 physics-only 诊断）插值到同一 HRRR 网格；同时给 AERO-AIR 和起报时刻 HRRR 持续性。10 个量为 Z/T×300、500、700、850、925 hPa；72 个时效完整值见 `colab03/texas_air_metrics.json`，下表只展示 72 h。\n')
lines.append('|组|变量|AERO-AIR 72 h RMSE|NeuralGCM 72 h RMSE|持续性 72 h RMSE|\n|---|---|---:|---:|---:|')
for g in ('strict','overlap'):
 for var in A['variables']:
  rm=A['groups'][g]['rmse']
  lines.append(f"|{g}|{var}|{rm['aero_air'][var][71]:.3f}|{rm['neuralgcm'][var][71]:.3f}|{rm['persistence'][var][71]:.3f}|")
lines.append('高空 Z 为位势高度（m），T 为 K；压力层对应同一格点、同一时刻的 NOAA HRRR wrfprs f00。此单未预先规定“更优”门槛，不把差值解释为原因。\n')
lines.append('## 输入冻结、局限与判定\n')
lines.append('`colab03/forecast.py:39–46,48–53` 仅以 `_read_era5_data(ids[0],1)` 读取起报时刻单帧并传 `ngcm.forward(...,include_era5_label=False)`；作者 `AERO_ODE_Dataset_v3.py:379–421` 用 `length=1` 切一个时间戳。`forecast.py:100–115` 先把预报张量全部物化，再在西部区分检验评分分支读取 HRRR；德州分支只存预测。NOAA 真值由 `colab03/metrics.py` 与 `metrics_high.py` 独立在预报完成后读入。核验对象为本次运行脚本和作者数据读取实现，不扩展为所有仓库入口。\n')
lines.append('程序化验收：2024-04-01…10 共 n=10、72 个时效、严格训练域外与重叠组均有近地面 RMSE、持续性、强风 P95/Top-k；高空 10 项有 AERO-AIR/NeuralGCM/持续性。按 Lead 10-22 事后修订的可执行口径②资料齐全；按 10-19 原口径，近地面 NeuralGCM 对照不可定义，故原判据②不能直接判“过”。修订偏离已批方案，待 Liang Hu 确认。①西部 n=10 原判据尚不过（9/14），故本报告不判整项“值得用/放弃”。\n')
lines.append('引用条目（请 Lead 补 PUBLIC_CITATIONS.md，不由本执行 bot 改）：Zhang et al. 2026, AERO-ODE, doi:10.1038/s41612-026-01555-w，Table 4 物理 PDF 第 15 页；AERO-ODE 官方代码 commit 99516ae9cf https://github.com/ZZzzzZZZV/AERO_ODE （Apache-2.0）；HF AERO_ODE_Case_Data https://huggingface.co/datasets/ZhangJing1106170090/AERO_ODE_Case_Data （CC-BY-NC-4.0）；NOAA HRRR 公共存储 https://noaa-hrrr-bdp-pds.s3.amazonaws.com/ （美国政府数据）；NeuralGCM 权重随作者案例（原始权重 CC-BY-SA-4.0）。\n')
path=B/'texas_zeroshot_colab03_v2.md'; assert not path.exists();path.write_text('\n'.join(lines))
print(path, len(lines), path.stat().st_size)
