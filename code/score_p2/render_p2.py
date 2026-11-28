#!/usr/bin/env python3
"""Render verified score JSON to report; never recompute or change verdict."""
import json,hashlib,sys
from pathlib import Path
p=Path(__file__).resolve().parent;m=json.loads((p/'metrics_p2.json').read_text());s=m['sources'];f=s['FOUR_v200_GFS'];v=f['primary']
def num(x):return 'NA' if x is None else f'{x:.4f}'
def span(x):return '['+', '.join(map(num,x))+']'
def fmt(z):return f"{num(z.get('PSS'))} / {num(z.get('POD'))} / {num(z.get('POFD'))} / {num(z.get('FAR'))}"
lines=['# R23.2d P2/P3 冻结预注册评分','',f"预注册 SHA-256 `{m['prereg_sha256']}`；冻结于 2026-11-11 18:43:56 EST。仅对 FOUR_v200_GFS、瑞士冻结 37 站、2024-10—2025-03 冷季、24–48 h 的站 P95 1 s 阵风告警下主判；本文件的其余比较不参与主判。",'','## E95 主判','',f"共同样本 {f['sample']['test']} 行，事件 {f['sample']['events']}，训练 {f['sample']['train']}，站数 {f['sample']['stations']}。PSS=POD−POFD，D=PSS(G1)−PSS(G0)。",'','| 方法 | PSS | POD | POFD | FAR | 命中 / 假警 |','|---|---:|---:|---:|---:|---:|']
for k,z in f['pooled']['methods'].items():lines.append(f"| {k} | {num(z['PSS'])} | {num(z['POD'])} | {num(z['POFD'])} | {num(z['FAR'])} | {z['hits']} / {z['false_alarms']} |")
lines+=['',f"D={num(v['D'])}；日块 10000 次 95% {span(v['day']['CI95'])}（有效 {v['day']['valid']}，{v['day']['blocks']} 日）；站块 10000 次 95% {span(v['station']['CI95'])}（有效 {v['station']['valid']}，{v['station']['blocks']} 站）。主判{'通过' if v['pass'] else '不过'}；两个区间上界均 <0.05：{'是' if v['resolves_negative'] else '否'}；两个上界均 <0（明显更差）：{'是' if v['clearly_worse'] else '否'}。",'','## 预注册必报副指标','', '以下方法格依次为 PSS / POD / POFD / FAR；检验事件 <10 的单站/阈值仅进合并、不单判。完整逐站与分层数值在 metrics_p2.json。','', '| 来源 / 分层 | 样本 / E95 | G0 | G1 | G2 |','|---|---:|---|---|---|']
for src,z in s.items():
 for label,g in [('合并',z['pooled'])]+[(f'lead={k} h',h) for k,h in z['by_lead'].items()]+[(f'地形={k}',h) for k,h in z['by_terrain'].items()]:lines.append(f"| {src} {label} | {g['n']} / {g['events']} | {fmt(g['methods']['G0'])} | {fmt(g['methods']['G1'])} | {fmt(g['methods']['G2'])} |")
lines+=['','Top-k 事件捕获率：前 ceil(0.05N) 行、前 E95 事件数行两档；共同样本按站/起报/时效破同分，随机按行期望 k/N。日块区间为重抽完整 UTC 验证日 10000 次。','', '| 来源 | 方法 | 档 | k | 捕获率 [日块 95%] | 随机按行期望 |','|---|---|---|---:|---:|---:|']
for src,z in s.items():
 for method,dd in z['pooled']['topk'].items():
  for kind,h in dd.items():lines.append(f"| {src} | {method} | {kind} | {h['k']} | {num(h['capture'])} {span(h['CI95'])} | {num(h['random_row_expectation'])} |")
lines+=['','Brier 技巧以各站训练季 E95 频率为 C；90% 覆盖率用该方法训练残差 q05–q95，按站类另列。冷季不能无证据称为非对流：缺闪电/焚风标签，灾种拆分不可做。','', '| 来源 / 地形 | 方法 | Brier | BSS 对 C | 90% 覆盖 |','|---|---|---:|---:|---:|']
for src,z in s.items():
 for label,h in [('合并',z['pooled'])]+list(z['by_terrain'].items()):
  for method in ['G1','G2']:
   q=h['methods'][method];lines.append(f"| {src} / {label} | {method} | {num(q['brier'])} | {num(q['BSS_vs_C'])} | {num(q['coverage90'])} |")
lines+=['','可靠性十箱（左闭右开；p=1 落最后一箱）：','', '| 来源 | 方法 | 箱 | n | 预测均值 | 实际频率 |','|---|---|---:|---:|---:|---:|']
for src,z in s.items():
 for method,boxes in z['pooled']['reliability'].items():
  for q in boxes:lines.append(f"| {src} | {method} | {q['bin']} | {q['n']} | {num(q['forecast_mean'])} | {num(q['observed_frequency'])} |")
lines+=['','3 s P95、1 s P99、工程绝对阈值：表头口径不等价；后者是观测事件相对站 P95 预警的情境诊断，不能视为对应工程阈值的专门概率预报。','', '| 情境 | 合并事件 | G0 PSS | G1 PSS | G2 PSS | <10 事件站数 |','|---|---:|---:|---:|---:|---:|']
for name,z in f['secondary'].items():
 if 'pooled' in z:lines.append(f"| {name} | {z['events']} | {num(z['pooled']['G0']['PSS'])} | {num(z['pooled']['G1']['PSS'])} | {num(z['pooled']['G2']['PSS'])} | {len(z['station_lt10'])} |")
 else:lines.append(f"| {name} | {z['events']} | {num(z['G0']['PSS'])} | 仅 E95 概率的排名 Top5={num(z['G1_rank']['capture'])} | 仅 E95 概率的排名 Top5={num(z['G2_rank']['capture'])} | 不单判 |")
supp=json.loads((p/'supplement_descriptive_p2.json').read_text())
lines+=['','补充的跨源情境表属于评分后描述性补算：对 E95 拟合的告警直接换观测事件标签，不能代替为该阈值重新训练、校准和选择 p*；因此只用于审计可得性，不据此判工程阈值技巧。','', '| 来源 / 情境 | n / 事件 | G0 PSS | G1 PSS | G2 PSS | <10 事件站数 |','|---|---:|---:|---:|---:|---:|']
for src,z in supp['by_source'].items():
 for name,h in z.items():
  u=h['pooled'];lines.append(f"| {src} / {name} | {u['n']} / {u['events']} | {num(u['G0']['PSS'])} | {num(u['G1']['PSS'])} | {num(u['G2']['PSS'])} | {len(h['station_lt10'])} |")
lines+=['','## M5 均风复验（GFS）','', '保留原设计 R / T0 / D2（留一站）与 M / M+D1（本站），五档时效按 P2 重新拟合；数值不可与 M5 原 12 站 2024-01—03、6/12/24/48 h 逐值等同。D2 对 T0 与 M+D1 对 M 均为相对 MAE 差，日块 10000 次。','', '| fhr h | n | R | T0 | D2 | M | M+D1 | (D2−T0)/T0 [95%] | (M+D1−M)/M [95%] |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for lead,z in m['M5'].items():
 q=z['MAE'];lines.append(f"| {lead} | {z['n']} | {num(q['R'])} | {num(q['T0'])} | {num(q['D2'])} | {num(q['M'])} | {num(q['M+D1'])} | {num(z['D2_vs_T0_relative'])} {span(z['D2_vs_T0_CI95'])} | {num(z['M+D1_vs_M_relative'])} {span(z['M+D1_vs_M_CI95'])} |")
lines+=['','M5 原冻结首试（12 站，2024-01—03）：fhr=24 h R/T0/D2/M/M+D1 的 MAE 分别为 2.811/3.066/2.050/1.637/1.477 m/s，D2 对 T0 −0.331 [−0.355,−0.309]；fhr=48 h 对应 2.844/3.098/2.076/1.671/1.546，D=−0.330 [−0.353,−0.307]。来源：06_Logs/r23_2_m5/results.md 第 9–16 行。','', '## 偏离与补定','']
for i,x in enumerate(m['deviations'],1):lines.append(f'{i}. {x}')
lines+=['','## 文件与会话','', '逐行预测 predictions_p2.csv.gz；M5 逐行 m5_predictions.csv.gz；拟合与退回详情 fits_p2.json；所有哈希见 archive_manifest_p2.json。原始配对表及站表只读。会话与 CU 在 session_p2.json 中逐项记录；其他账户会话的 CU 不归入本任务。','']
if (p/'session_p2.json').exists():
 z=json.loads((p/'session_p2.json').read_text());lines.append('会话记录：'+json.dumps(z,ensure_ascii=False))
(p/'results_p2.md').write_text('\n'.join(lines)+'\n');print(p/'results_p2.md')
