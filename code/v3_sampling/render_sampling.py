#!/usr/bin/env python3
"""Render R23.3a-05 table strictly from saved paired CSV on Colab CPU."""
import csv,json,hashlib,statistics
from collections import Counter
from pathlib import Path
P=Path('/content'); data=list(csv.DictReader((P/'sampling_rows.csv').open())); s=json.loads((P/'sampling_summary.json').read_text());m=s['metrics']
assert len(data)==69 and len({(r['event'],r['station']) for r in data})==69
assert len([r for r in data if r['status']=='paired'])==s['paired']
source=(P/'a_v3_r2_main.csv').read_bytes(); digest=hashlib.sha256(source).hexdigest()
lines=['# R23.3a-05 观测采样口径诊断（仅 v3 (a) 主池）','',
'定义：对同一站–事件、同一 t* 与同一模型峰，e = pred_peak_10m / obs_peak_10m − 1；B = median(e)；M = median(|e|)。小时观测直接取冻结后成功运行的 `a_v3_r2_main.csv` 中 `observed_10m_sknt`，不重算。分钟观测取 IEM `asos1min.py` 的 `sknt`（逐分钟发布的约 2 min 平均持续风，非阵风），峰乘相同 `height_factor`。d = obs_hour − obs_min，单位 kt；ΔB = B_hour − B_min、ΔM = M_hour − M_min，单位百分点。', '',
'窗口与 `prereg_v3/chain_a_v3_r1.py` 第 26–52 行一致：UTC 登陆时间减 12 h 后向下取整到整点，起始整点起 24 个小时格 `[start,start+24 h)`；若模型峰 t* 向下取整小时后，t* 的前 2、前 1、所在及后 1 小时格超出基窗，取两者的并集。每个小时格对应整点至下一整点的 60 个分钟，左闭右开；窗口及分钟总数逐站写在 CSV。分钟 `sknt` 有限且 ≥0 的不同分钟数 / 窗口应有分钟数 ≥90% 才配对；否则标记分钟截尾，已观测峰只作下界，不计误差。IEM 每条请求 URL、HTTP 状态、原始行数及有效分钟数见 `requests.csv`。', '',
'本诊断不是重新冻结 v3，不判 ±20% 闸；保留 v3 15×3 缺站的“不判闸”。高度依旧是 2025 清单代理，事件时历史高度未证实。此处 `sknt` 两种产品名义上均指约 2 min 平均风，比较的是取样/报文资料可用性口径，不是独立传感器实验。','',
f'输入：v3 主池 69 个已有小时观测可评站–事件，源 CSV SHA-256 `{digest}`。同站共同可配对 {s["paired"]}/69；分钟截尾 {s["status_counts"].get("minute_censored",0)}、一分钟无有效资料 {s["status_counts"].get("unavailable",0)}、请求失败 {s["status_counts"].get("fetch_error",0)}。下表所有误差重新在共同可配对的同一批站上计算，不拿原 69 站 B=+35.98% 与子集结果直接相减。','',
'| 同站共同子集 | 小时 METAR | 一分钟 ASOS | 小时−分钟 |','|---|---:|---:|---:|',
f'| B = median(e) | {m["B_hour"]*100:+.2f}% | {m["B_min"]*100:+.2f}% | {m["B_hour"]*100:.2f}−{m["B_min"]*100:.2f}={m["delta_B"]*100:+.2f} pp |',
f'| M = median(\u007ce\u007c) | {m["M_hour"]*100:.2f}% | {m["M_min"]*100:.2f}% | {m["M_hour"]*100:.2f}−{m["M_min"]*100:.2f}={m["delta_M"]*100:+.2f} pp |','',
f'配对 d<0：{m["d_negative"]}/{s["paired"]}；d 的 Q1 / 中位数 / Q3 = {m["d_q1"]:.2f} / {m["d_median"]:.2f} / {m["d_q3"]:.2f} kt。四分位采用排序后 `(n−1)p` 位置线性插值。','',
'| 事件 | 69 站候选数 | 可配对 | 分钟截尾 | 一分钟不可得 |','|---|---:|---:|---:|---:|']
for event in sorted(set(r['event'] for r in data)):
 a=[r for r in data if r['event']==event]; c=Counter(r['status'] for r in a)
 lines.append(f'| {event} | {len(a)} | {c["paired"]} | {c["minute_censored"]} | {c["unavailable"]+c["fetch_error"]} |')
lines+=['','## 未配对明细（下界是已观测一分钟峰乘同一高度因子；无有限上界）','','| 事件 | 站 | 原始行 / 有效分钟 / 窗口分钟 | 原因 | 已观测峰 10 m 下界 (kt) |','|---|---|---:|---|---:|']
for r in sorted(data,key=lambda r:(r['event'],r['station'])):
 if r['status']=='paired':continue
 lower= f'{float(r["minute_peak_10m_lower_bound_kt"]):.2f}' if r['minute_peak_10m_lower_bound_kt'] else '无有效分钟，未定义'
 lines.append(f'| {r["event"]} | {r["station"]} | {r["response_rows"]} / {r["valid_minutes"]} / {r["window_minutes"]} | {r["status"]}: {r["reason"]} | {lower} |')
lines+=['','结论仅限这套 v3 配置与能同时取得两种观测的站–事件：共同子集上的 ΔB、ΔM 是配对描述差，不等于 v1(+9.9%) 和 v3(+35.98%) 跨版本、跨站集差异的因果分解；缺测选择与不同模型配置未被控制。','',
'逐站指标、时窗与分钟覆盖：`sampling_rows.csv`；逐请求 URL/行数：`requests.csv`；程序摘要：`sampling_summary.json`；Colab CPU 执行日志和退出码：`sampling.log`、`sampling.exit`；计算脚本：`sampling_worker.py` 与 `render_sampling.py`。']
(P/'RESULTS_sampling.md').write_text('\n'.join(lines)+'\n')
print('written',len(lines),'lines, source sha',digest)
