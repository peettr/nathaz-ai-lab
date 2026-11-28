#!/usr/bin/env python3
"""Render secondary-only metrics after verified Colab archive and teardown."""
import json,hashlib,sys
from pathlib import Path
p=Path(__file__).resolve().parent
x=json.loads((p/'metrics_sec.json').read_text());s=json.loads((p/'session_sec.json').read_text())
def fmt(v):return '—' if v is None else f'{v:.4f}'
lines=['# R23.2d 冻结预注册副指标补算（只报不判）','',f"数据：`pairs_p2.csv.gz`，SHA-256 `{x['input_sha256']}`；训练观测按 (station, valid_end_utc) 去重 {x['training_unique_observation_count']} 条。检验季为冷季 3；FOUR 是主来源，GRAP/PANG 仅并列报告。不改冻结 E95 主判及已有 score_p2 文件。",'', '## 阈值口径与站内样本','', 'E99 与 E95_3s 分别用去重训练观测的本站 1 s P99、3 s P95；工程阈值绝对值见表头。检验事件数为配对行数，同一有效时刻可被多提前量重复；unique 列为本站×有效时刻去重事件数。站×阈值检验事件不足 10 的站只进合并、没有单站判定。G0c 事后补充，不参加主判。','', '| 来源 | 事件 | n / 事件行 / 独立时刻 | <10 站数 | G0 PSS | G1 PSS | G2 PSS | G0c PSS |','|---|---|---:|---:|---:|---:|---:|---:|']
for src,v in x['sources'].items():
 for name,z in v.items():
  m=z['pooled']['methods'];lines.append(f"| {src} | {name} | {z['n_test']} / {z['pooled']['events']} / {z['unique_test_events']} | {len(z['station_lt10'])} | "+' | '.join(fmt(m[k]['PSS']) for k in ['G0','G1','G2','G0c'])+' |')
lines+=['','## 全部方法指标：合并与按地形类','', '每个事件和来源均报告 PSS、POD、POFD、FAR、Top-k（5% 与事件行数 k）、Brier/BSS。G0 是数值阵风或均风，无概率与 Brier/BSS。Top-k 采用确定性同分破平，捕获率的分母是该组的事件行数。','', '| 来源 | 事件 | 分组 | 方法 | n / 事件 | PSS | POD | POFD | FAR | Top5% k / 捕获 | Top事件数 k / 捕获 | Brier | BSS对C |','|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for src,v in x['sources'].items():
 for name,z in v.items():
  for group,q in [('合并',z['pooled'])]+list(z['by_terrain'].items()):
   for method,m in q['methods'].items():
    t=m['topk'];a=t['5pct'];b=t['events'];lines.append(f"| {src} | {name} | {group} | {method} | {q['n']}/{q['events']} | "+' | '.join(fmt(m[k]) for k in ['PSS','POD','POFD','FAR'])+f" | {a['k']}/{fmt(a['capture'])} | {b['k']}/{fmt(b['capture'])} | {fmt(m['brier'])} | {fmt(m['BSS_vs_C'])} |")
lines+=['','## 与原副表口径的差、偏离与补定','', '原 `score_p2` 的 E99/3 s 未按各自阈值重拟 G1/G2 概率，工程阈值的 G1/G2 则沿用 E95 告警；旧 G1/G2 PSS 不可当作各事件的专门拟合技巧。旧 E99/3 s G0 直接按各自阈值告警，旧工程阈值 G0 误沿用 E95 告警。上表对每个事件重算概率和训练季 p*；原冻结主判不改。','','原 3 s 第一表事件 2608、跨源补表事件 2603：`score_p2.py` 第 133–135 行按 FOUR 与 GFS 特征同时完整的训练共同样本算站 P95；`supplement_p2.py` 第 7–13 行按 FOUR 观测完整但不要求预报特征完整的训练行算站 P95。两者训练样本过滤不同，阈值微移；第 15–24 行都在同一冻结检验预测表换标签。新口径统一使用按 (station,valid_end_utc) 去重的训练观测，各源见上表；这是阈值口径差，不是 5 个独立事件凭空消失。','','原口径与本次的具体事件数/PSS 差（FOUR，合并）：','', '| 事件 | 原事件行 | 新事件行 | 新减原 | 原 G0 PSS | 新 G0 PSS | 新减原 |','|---|---:|---:|---:|---:|---:|---:|']
old=json.loads((p.parent/'score_p2'/'metrics_p2.json').read_text())['sources']['FOUR_v200_GFS']['secondary']
for name,z in x['sources']['FOUR_v200_GFS'].items():
 if name in old:
  oldz=old[name];oe=oldz.get('events'); om=oldz.get('G0',oldz.get('pooled',{}).get('G0'));ov=om['PSS'] if om else None; nv=z['pooled']['methods']['G0']['PSS'];lines.append(f"| {name} | {oe} | {z['pooled']['events']} | {z['pooled']['events']-oe} | {fmt(ov)} | {fmt(nv)} | {fmt(nv-ov) if ov is not None and nv is not None else '—'} |")
lines+=['', '补定：G0c 按事后对照定义采用本站×GFS 风向扇区 OLS；均风情境则把 GFS 10 m 风速代入同一校准结构，而 G0 用原始 GFS 10 m 风速。G1 对 3 s 或均风重新拟合相应观测目标，其余阵风阈值共享连续阵风 OLS 系数但分别重算残差超阈概率和 p*。G2 仍以本站训练季阈值生成留出站概率，是偏乐观参考。训练内残差与训练内选 p* 可能乐观；站类不是灾种，不能推论工程可用性。','', '逐站 <10 事件清单：','']
for src,v in x['sources'].items():
 for name,z in v.items():lines.append(f"- {src} / {name}：{', '.join(z['station_lt10']) or '无'}")
lines+=['','## 运行与验证','',f"Colab CPU 会话：{s['name']}；分配 {s['start_est']}，停止 {s['stop_time']}（美东）；分配时长 {s['duration_hours']} h，按 {s['rate_cu_per_hour']} CU/h 估算 {s['estimated_CU']} CU（非独立账单）。stop 返回：{s['stop_response']}。停后私有列表：{s['private_sessions_after']}；全局列表：{s['global_sessions_after']}。",f"逐行表 `predictions_sec.csv.gz` SHA-256 {s['predictions_sha256']}，共 {s['prediction_rows']} 行；指标 JSON SHA-256 {hashlib.sha256((p/'metrics_sec.json').read_bytes()).hexdigest()}。远端日志与拉回记录在本目录；0 SU。",'','## 结论','','以上均为只报不判的阈值专门副指标，不改变冻结 E95 主判或六审裁决。']
(p/'results_sec.md').write_text('\n'.join(lines)+'\n')
print(p/'results_sec.md')
