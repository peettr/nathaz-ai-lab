#!/usr/bin/env python3
"""Render the immutable v2 scorer outputs; no scientific refitting."""
from pathlib import Path
import csv, json, math, hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
R=Path(__file__).parent
S=R/'score_v2'
g=json.loads((S/'gate.json').read_text())
assert (S/'score.done').read_text().strip()=='success' and not (S/'score.failed').exists()
assert g['train_rows']==17604 and g['test_rows']==17252 and len(g['D'])==4
with (S/'scores.csv').open() as f: rows=list(csv.DictReader(f))
with (S/'station_mae.csv').open() as f: stations=list(csv.DictReader(f))
with (S/'terrain_mae.csv').open() as f: terrain=list(csv.DictReader(f))
with (S/'coverage.csv').open() as f: cover=list(csv.DictReader(f))
with (S/'condition_numbers.csv').open() as f: cond=list(csv.DictReader(f))
assert len(stations)==48 and len(cover)==192 and len(cond)==48 and len(terrain)==24
idx={(int(x['fhr']),x['metric']):x for x in rows}
fh=(6,12,24,48)
assert set(int(x['fhr']) for x in stations)==set(fh)
assert len({x['site'] for x in stations})==12
assert set(int(x['fhr']) for x in g['D'])==set(fh)
assert len(rows)==324 and all((h,'D') in idx for h in fh)
assert all(float(idx[h,'D']['hi'])<0 for h in fh) and g['pass'] and not g['stop']
pred=pd.read_parquet(S/'paired_predictions.parquet')
assert len(pred)==g['test_rows']
assert set(pred.fhr)==set(fh)
assert len(pred[['site','init_utc','fhr']].drop_duplicates())==len(pred)
assert pred.groupby('fhr').size().to_dict()=={h:int(idx[h,'D']['n']) for h in fh}
now=datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M EST')
def num(x,d=3):return f'{float(x):.{d}f}'
def ci(x,d=3):return f"{num(x['point'],d)} [{num(x['lo'],d)}, {num(x['hi'],d)}]"
lines=['# M7 FuXi-CFD 瑞士 12 站全量首试 · 最终评分',f'生成时间 {now}；评分为 `score_v2/` 的冻结主判事后实现修复版。原预注册判据未改。','',
'预注册 `R23.2-05 M7 FuXi-CFD 降尺度层预注册.md` sha256 `5360c303cf351a5d29593e615455038030cddddf6de35fe51dc768cdee41d59a`；评分脚本 `score_m7_local_v2.py`。原始 `score/score.failed` 是缺少归档 issue 列的首次失败，未生成分数；v2 从原始 init 按 M5 固定 +4 h 构造 issue/cutoff，不等于独立存档的发布时间。',
'', '全量推理 35036/35036 行、失败 0，GPU 新推理 34540 次（496 行首项复用）；均值 0.0509076 s；全量运行墙时 3193.769 s。训练 17604 行，按 issue 边界检验 17252 行；原归档检验 17432 行，其余边界行不计分。四起报时次未降档。',
'', '## 主判', 'D(L)=(MAE_FXD2−MAE_D2)/MAE_D2；各日同日全站整块重抽 1000 次，95% 配对区间；L=fhr−4 h。',
'| fhr / L (h) | n / 日 | D2 MAE (m/s) | FXD2 MAE (m/s) | D(L) [95%] | 判定 |', '|---|---:|---:|---:|---:|---|']
for h in fh:
 x=idx[h,'D'];lines.append(f"| {h} / {h-4} | {x['n']} / {x['days']} | {num(idx[h,'MAE_D2']['point'])} | {num(idx[h,'MAE_FXD2']['point'])} | {ci(x,4)} | 更好（上界<0） |")
lines+=['', '四个时效的上界均小于零，满足预注册的「至少一个」通过判据；不触发「四档上界全部 ≥0」止损。相对增益只约 2.2–2.6%，不把本次单配置结论外推为 FuXi-CFD 普遍优越。',
'','## 副指标：配对 MAE 差 (m/s)','负值表示前者误差较小；同检验日全站整块区间。','| fhr | FX0−R | FX-T0−T0 | FX-T0−D2 | (M+D1+FX)−(M+D1) |','|---|---:|---:|---:|---:|']
for h in fh:
 lines.append('| '+str(h)+' | '+' | '.join(ci(idx[h,m]) for m in ('delta_FX0_minus_R','delta_FX-T0_minus_T0','delta_FX-T0_minus_D2','delta_M+D1+FX_minus_M+D1'))+' |')
lines+=['','## 分站 MAE (m/s)','每格 D2 / FXD2 / FX0；站点分层为描述性指标。','| 站 (类, Δz m) | fhr6 | fhr12 | fhr24 | fhr48 |','|---|---:|---:|---:|---:|']
for site in sorted({x['site'] for x in stations}):
 d={int(x['fhr']):x for x in stations if x['site']==site};v=d[6]
 lines.append(f"| {site} ({v['terrain']}, {num(v['dz'],1)}) | "+' | '.join('/'.join(num(d[h]['MAE_'+m],2) for m in ('D2','FXD2','FX0')) for h in fh)+' |')
lines+=['','## 地形和高差分组 MAE (m/s)','每格 D2 / FXD2 / FX0；四地形类每类 3 站，Δz 正 7 站、负 5 站。','| 组 | fhr6 | fhr12 | fhr24 | fhr48 |','|---|---:|---:|---:|---:|']
for group in ('terrain','dz'):
 for name in (('pass','plateau','ridge','valley') if group=='terrain' else ('positive','negative')):
  d={int(x['fhr']):x for x in terrain if x['group']==group and x['class']==name}
  lines.append(f'| {group}:{name} ({d[6]["stations"]}站) | '+' | '.join('/'.join(num(d[h]['MAE_'+m],2) for m in ('D2','FXD2','FX0')) for h in fh)+' |')
lines+=['','## 强风判别（站点原生 10 分钟训练 P95）','AUC 为站内 12 站等权平均（主口径）/跨站合并（描述性）。每格点值 [日块95%区间]。强风原生阈值见 `score_v2/native_thresholds.json`。','| fhr | D2 站内 / 合并 | FXD2 站内 / 合并 | FX0 站内 / 合并 |','|---|---:|---:|---:|']
for h in fh:lines.append('| '+str(h)+' | '+' | '.join(ci(idx[h,'station_mean_AUC_'+m])+' / '+ci(idx[h,'AUC_'+m]) for m in ('D2','FXD2','FX0'))+' |')
lines+=['','Top-k：每个时效分别从全网行中按预测风速排序（不是逐站排名）；按条=捕获的事件行占全体事件行，按事件=捕获至少一行的事件 ID 占全体事件 ID。每格点值 [日块95%区间]，完整的 R、T0、FX-T0、M+D1、M+D1+FX 结果在 `score_v2/scores.csv`。','| fhr | k | D2 行 / 事件 | FXD2 行 / 事件 | FX0 行 / 事件 | 随机期望 行 / 事件 |','|---|---:|---:|---:|---:|---:|']
for h in fh:
 d=pred[pred.fhr==h];N=len(d)
 event_counts=d.loc[d.event].groupby('event_id').size().to_numpy();E=len(event_counts)
 assert E>0
 for k in (1,5,10):
  K=max(1,math.ceil(N*k/100))
  # P(any event row sampled without replacement) = 1 - C(N-m,K)/C(N,K)
  expected=sum(-math.expm1(sum(math.log1p(-int(m)/(N-i)) for i in range(K))) if N-int(m)>=K else 1.0 for m in event_counts)/E
  lines.append('| '+str(h)+f' | {k}% | '+' | '.join(ci(idx[h,f'Top{k}_'+m])+' / '+ci(idx[h,f'eventTop{k}_'+m]) for m in ('D2','FXD2','FX0'))+f' | {K}/{N}={K/N:.4f} / {expected:.4f} |')
lines+=['','## 预测区间覆盖率','训练期其他 11 站残差分位数造 80%/90% 名义区间。每格为实际合并覆盖率 [日块95%区间]，逐站原始值见 `score_v2/coverage.csv`。瑞士冷季全归「非对流大风」为未核验假设，故灾种分开只有该类。','| fhr | D2 80% | FXD2 80% | D2 90% | FXD2 90% |','|---|---:|---:|---:|---:|']
for h in fh:lines.append('| '+str(h)+' | '+' | '.join(ci(idx[h,f'cover{k}_'+m]) for k in (80,90) for m in ('D2','FXD2'))+' |')
lo=min(float(x['condition']) for x in cond);hi=max(float(x['condition']) for x in cond)
lines+=['','## 实现与未完成项',f'主设计矩阵 48 折条件数范围 {lo:.3e}–{hi:.3e}，均 >1e6：模型包含截距与四个互斥且穷尽的地形哑元，存在精确线性依赖。按预注册另做「去截距、保留四类哑元」敏感性；其主判点值在四档分别为 −0.02643051、−0.02503097、−0.02262731、−0.02227250，与主判在浮点精度内一致；去截距条件数范围约 9.49e3–1.49e4。该敏感性未重新 bootstrap 区间，不冒充独立确认。',
'延迟 6 h 敏感性未评估：须重新选最新可用 GFS 运行并生成相应 FX，不能仅改 issue 标签；本会话已停止，不重启 Colab。',
'实际任务 CU 无法从共享 Colab 账户余额独立核算：没有可归因的会话级账单和已核验停机时间/独占费率。首项的 23.54 CU 是运行前保守外推，不能当实际消耗；全量新推理墙时约 0.887 h，不包含分配、首项、下载与停机，不能当计费时长。已知首项分配时间 14:55:47 EST，16:12:22 EST 保活确认推理完成但会话仍分配；此前会话已停止，不应以推理耗时×6.81 构造「实际 CU」。本项 HPC=0 SU。',
'粗糙度统一 z0=0.01 m、9×9 粗格的 UTM ±4 km / 1 km 间距、偶数网格中心 (149,149) 等是已登记的工程假设；GFS 驱动不等于论文的 ERA5 驱动。',
'','原始逐行输出 `full_fx_rows_1107_161219.jsonl`；复算配对小检查点 `score_v2/paired_predictions.parquet`；原始推理总结 `full_final/summary.json`；评分 `score_v2/scores.csv`、`score_v2/gate.json`、`score_v2/station_mae.csv`、`score_v2/terrain_mae.csv`、`score_v2/coverage.csv`、`score_v2/condition_numbers.csv`。']
out=R/'final_report.md'
assert not out.exists(),'do not overwrite final report'
out.write_text('\n'.join(lines)+'\n')
print(out, 'rows',len(lines),'sha256',hashlib.sha256(out.read_bytes()).hexdigest())
