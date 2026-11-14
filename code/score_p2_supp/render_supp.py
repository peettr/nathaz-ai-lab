#!/usr/bin/env python3
"""Render the corrected, post-hoc attribution comparison from verified JSON."""
import json, pathlib, hashlib
p=pathlib.Path(__file__).parent
m=json.loads((p/'metrics_supp_corrected.json').read_text())
f=lambda x:'—' if x is None else f'{x:.4f}'
lines=['# P3 事后补充对照（不参加冻结主判）','', '仅对同一来源、同一训练/检验季与共同样本比较。G1 是只读冻结预测，不重拟；G0 为未校准 GFS GUST 原值。G0c 按 GFS 10 m 风向分扇区；G1a/G1g 沿用 G1 的 AI 风向扇区，仅替换预测因子。每站×扇区不足 30 条回退本站全部训练季。概率为训练内 OLS 残差经验超阈率；p* 由训练内 PSS 的 0.05–0.95 步长 0.05 网格选取。', '', '## 五方法指标（E95）','', '| 来源 | 方法 | N/事件 | PSS | POD | POFD | FAR | Brier | BSS(训练季站点气候) | Top 5% 捕获 | Top 事件数捕获 |','|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for s,x in m['sources'].items():
 o=x['pooled'];
 for name,met in o['methods'].items():
  top=o['topk'][name];lines.append(f"| {s} | {name} | {o['n']}/{o['events']} | {f(met['PSS'])} | {f(met['POD'])} | {f(met['POFD'])} | {f(met['FAR'])} | {f(met['brier'])} | {f(met['BSS_vs_C'])} | {f(top['5pct']['capture'])} | {f(top['events']['capture'])} |")
lines += ['', 'G0 是速度而非概率，Brier/BSS 不适用；Top-k 以速度排序。Top-k 相同分数按站、起报、提前量破同分；5% 的 k 向上取整。BSS 以冻结训练季站点气候概率为参照。', '', '## 四组配对 PSS 差（B=10000，种子 20261111）','', '| 来源 | 差值 | 点值 | 验证 UTC 日块 95% CI (181块) | 站点块 95% CI (37块) |','|---|---|---:|---|---|']
for s,x in m['sources'].items():
 for k,v in x['contrasts'].items():
  day=x['CI95']['day']['contrasts'][k]['CI95'];st=x['CI95']['station']['contrasts'][k]['CI95'];lines.append(f'| {s} | {k} | {f(v)} | [{f(day[0])}, {f(day[1])}] | [{f(st[0])}, {f(st[1])}] |')
lines += ['', '## 逐提前量、按站类（PSS、POD、POFD、FAR、Brier、BSS 与 Top-k）','']
for s,x in m['sources'].items():
 lines += [f'### {s}', '', '| 分组 | N/事件 | 方法 | PSS | POD | POFD | FAR | Brier | BSS | Top5% | Top事件数 |','|---|---:|---|---:|---:|---:|---:|---:|---:|---:|']
 for label,groups in [('提前量',x['by_lead']),('站类',x['by_terrain'])]:
  for g,o in groups.items():
   for name,met in o['methods'].items():
    top=o['topk'][name];lines.append(f"| {label} {g} | {o['n']}/{o['events']} | {name} | {f(met['PSS'])} | {f(met['POD'])} | {f(met['POFD'])} | {f(met['FAR'])} | {f(met['brier'])} | {f(met['BSS_vs_C'])} | {f(top['5pct']['capture'])} | {f(top['events']['capture'])} |")
 lines.append('')
lines += ['## 站内标准化 G0 Top-k','', '本站训练季 GFS GUST 右连续经验百分位作为排序分数，仅改变 Top-k 排序、不改变 G0 二值告警；不跨源混排。', '', '| 来源 | N/事件 | Top 5% k/捕获 | Top 事件数 k/捕获 |','|---|---:|---:|---:|']
for s,x in m['sources'].items():
 z=x['pooled']['topk']['G0_station_percentile'];lines.append(f"| {s} | {x['sample']['test']}/{x['sample']['events']} | {z['5pct']['k']}/{f(z['5pct']['capture'])} | {z['events']['k']}/{f(z['events']['capture'])} |")
lines += ['', '## 口径、偏离与版本','', '第一版错误地用 AI 风向扇区拟合 G0c，已保留原 metrics_supp.json、predictions_supp.csv.gz、score_supp_initial.py 作为无效历史尝试；本报告仅引用 metrics_supp_corrected.json 和 predictions_supp_corrected.csv.gz，原版绝不可用于科学结论。因不得覆盖已有结果，正式正确文件使用 corrected 后缀；这一点与任务书指定的无后缀 JSON 文件名不一致，需 Lead/Liang Hu 明确批准替换后才可改名。', 'G0c 采用 GFS 风向，G1a/G1g 采用 AI 风向（任务书“同 G1a”保守读法）；因此 G1a−G1g 是同一扇区比较，G1−G0c 包含方向扇区定义的差异，不能单独解释为 AI 风速的因果效应。G1 对照 G0c 的增益亦包含两预测因子的交互和方向差异，不是独立 AI 主效应。', '输出仅为事后补充，不参与、不重判冻结主判。训练内残差与 p* 沿用原 G1 的乐观训练口径；站点自助单位为站，日块按验证 UTC 日；每组同一重抽索引计算两个方法的配对 PSS 差。', '', '## 数据与运行','', '输入：../pairs_p2.csv.gz、../score_p2/predictions_p2.csv.gz（只读）。脚本 score_supp.py（正确版本）、render_supp.py；归档 manifest_supp_corrected.json。三源共 196651 行逐行预测，corrected 压缩表及 JSON 的 SHA-256 与远端清单逐个核对。', 'Colab CPU r232d-p3supp-1111：美东 2026-11-11 约 19:00 分配，19:06:57 前已执行 stop 返回 Session terminated；私有与全局 sessions 均仅列出不相关 L4，会话不再列出。按本会话约 7–8 分钟、既有 CPU 约 0.08 CU/h 估计约 0.009–0.011 CU，非独立账单；账户 1104.94→1104.77 CU 含并行 L4，不归因于本任务。0 SU。', '', '## 事后结论','', 'FOUR 的 G0c−G0 大幅为正，但 G1−G0c 的日块与站块区间均跨 0；G1a−G0c、G1a−G1g 两种区间均小于 0。由此不能把冻结主判的巨大 G1−G0 差值归为 AI 风速的独立贡献；本站校准解释了主要差距。GRAP/PANG 的 G1−G0c 同样两种区间跨 0；它们 G1a−G1g 的两种区间跨 0。', '']
(p/'results_supp.md').write_text('\n'.join(lines))
print(p/'results_supp.md')
