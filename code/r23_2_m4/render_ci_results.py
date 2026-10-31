#!/usr/bin/env python3
"""Append Colab-computed post-hoc intervals to the existing final report."""
import csv
from pathlib import Path
root=Path(__file__).resolve().parent
base=root/'ci_20261025'
def load(name):
    with (base/name).open(newline='') as f:return list(csv.DictReader(f))
a=load('secondary_ci.csv'); b=load('increment_ci.csv')
assert len(a)==378 and len(b)==288
assert {(x['network'],int(x['lead_min']),x['method'],x['metric']) for x in a}=={(n,l,m,k) for n in ('OKC','Swiss') for l in (10,20,30,60,120,180,240,300,360) for m in ('P','F','B') for k in ('auc','topk_rows_1','topk_events_1','topk_rows_5','topk_events_5','topk_rows_10','topk_events_10')}
assert {(x['network'],int(x['lead_min']),x['contrast'],x['metric']) for x in b}=={(n,l,c,k) for n in ('OKC','Swiss') for l in (10,20,30,60,120,180,240,300,360) for c in ('B-P','B-F') for k in ('mae','auc','topk_rows_1','topk_events_1','topk_rows_5','topk_events_5','topk_rows_10','topk_events_10')}
fmt=lambda x:f"{float(x['point']):+.4f} [{float(x['lo']):+.4f},{float(x['hi']):+.4f}]"
parts=['\n### 事后补定 10-25：副指标与接口 §6 分段增量区间（主判不变）\n',
'冻结 `m4_score.py`、预注册和接口均未修改。新脚本 `m4_score_ci.py` SHA256 `2a82c9d8218559370a5d38d898a7e8d4f8da0fba8ebf3115083a0dfb97163706`；仅用已归档 `pairs/` 内两网 GFS delay4 的逐行检验配对，先逐项复核 P/F/B 的原始 AUC 与三个 k 的条/事件点估计与冻结 `output_v3/*secondary.csv` 一致（容差 1e-12）。同一网、同一提前量按 issue UTC 检验日整块有放回抽 1000 次，种子 `230202+L+4×10000`；同一抽样用于 P/F/B 和差值，报告 2.5/97.5 百分位。强风阈值及事件 ID 沿冻结评分；重复抽到同一天不另造事件，跨日事件仍沿完整观测 ID。两网 GFS 4h 各 9 档、P/F/B、AUC 与 1/5/10% 条/事件：`ci_20261025/secondary_ci.csv` 共 378 行点估计和区间；B−P 与 B−F 的 MAE/AUC/Top-k：`ci_20261025/increment_ci.csv` 共 288 行。负 MAE 增量有利于 B，正 AUC/捕获率增量有利于 B；副指标区间为事后补定，不改变预注册 D(L) 主判。']
labels={'mae':'MAE（m/s）','auc':'强风 AUC','topk_rows_1':'Top-1% 条','topk_events_1':'Top-1% 事件','topk_rows_5':'Top-5% 条','topk_events_5':'Top-5% 事件','topk_rows_10':'Top-10% 条','topk_events_10':'Top-10% 事件'}
idx={(x['network'],int(x['lead_min']),x['contrast'],x['metric']):x for x in b}
for net in ('OKC','Swiss'):
    parts.append(f'\n{net}（每格差值点估计 [95% 下限,上限]；B 相对 P / F 为同一日块配对差）：\n')
    for metric,title in labels.items():
        parts.append(f'\n{title}：\n\n| L/min | B−P | B−F |\n|---|---|---|')
        for lead in (10,20,30,60,120,180,240,300,360):
            parts.append(f"| {lead} | {fmt(idx[net,lead,'B-P',metric])} | {fmt(idx[net,lead,'B-F',metric])} |")
parts += ['\n在本次补充区间中，瑞士 B−P 的 AUC 九档区间均低于 0；Top-k 的条与事件区间并非每档均低于 0，不能把点估计符号说成显著差异。完整 P/F/B 自身 95% 区间以 `secondary_ci.csv` 为准，不能以两个独立区间端点相减代替配对差区间。原 06:30“缺 AUC/Top-k 区间”的陈述是当时的中间状态，现由本节及两张表补齐，不把此补定写回冻结主判。']
report=root/'results.md'; old=report.read_text(); tag='### 事后补定 10-25：副指标与接口 §6'
assert tag not in old
report.write_text(old+'\n'+'\n'.join(parts)+'\n')
print('appended',len(parts),'segments',len(b),'increment rows',len(a),'secondary rows')
