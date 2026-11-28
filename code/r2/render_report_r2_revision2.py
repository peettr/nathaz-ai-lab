"""Render D yawfix r2 report exclusively from checked JSON results."""
import json,sys,statistics
from pathlib import Path
new=json.loads(Path(sys.argv[1]).read_text())
old=json.loads(Path(sys.argv[2]).read_text())
out=Path(sys.argv[3]);assert not out.exists()
assert new['completed_storm']==360 and new['completed_stationary']==36
rules=new['rules'];assert len(rules)==10 and len(new['seeds'])==12
paths=['I_near','III_kzm05','III_kzm00']
assert set(new['gates'])==set(paths)
fmt=lambda n:f'{n:+.2f}' if n is not None else '—'
labels={'I_near':'Case I','III_kzm05':'Case III kzm=.05','III_kzm00':'Case III kzm=0'}
keys=[('tower_top_yaw_absmax_kNm','偏航力矩'),('tower_fore_aft_negative_magnitude_kNm','塔底前后负峰'),('blade_root_negative_magnitude_kNm','三叶根面外负峰')]
lines=['# A3 分段 D · 偏航限速第二轮（修订2事后例外）','', '数据源：本次 metrics_D_yawfix.json；对照：原 metrics_D.json。所有表格数值从 JSON 生成，非手抄。','', '## 运行与限速','',f"完整风暴运行 {new['completed_storm']}/{new['expected_storm']}；稳态 NoStop {new['completed_stationary']}/{new['expected_stationary']}；三路径×12 种子×10 规则、18/20/22 m/s 各 12 稳态窗。",f"高精度 ES NacYaw 1 s 割线最大（含稳态）{max([new['stationary_yaw_max_deg_s']]+[new['gates'][c]['yaw_rate_max_deg_s'] for c in paths]):.5f}°/s；有 {len(new['rate_exceptions'])} 次 >0.31°/s，均 S3_30，故全运行限速修复未通过（修订2事后允许分列并重判）。YawDOF=True，Y_Rate=0.24°/s。",'', '## G2L 对 G1 配对中位降幅（%）与旧 D 对照','', '| 路径 | 指标 | 原 D | 修正 D |', '|---|---|---:|---:|']
for c in paths:
 for k,label in keys:
  a=old['summaries'][c]['G2L']['metrics'][k]['median_reduction_pct'];b=new['summaries'][c]['G2L']['metrics'][k]['median_reduction_pct'];lines.append(f'| {labels[c]} | {label} | {fmt(a)} | {fmt(b)} |')
lines.extend(['','## 十规则配对中位降幅、误停窗、组最大偏航速率','', '| 路径 | 规则 | 偏航旧→新 (%) | 塔负峰旧→新 (%) | 三叶根负峰旧→新 (%) | 误停旧→新 /36 | 最大 1s 割线旧→新 (°/s) |','|---|---|---:|---:|---:|---:|---:|'])
for c in paths:
 for g in rules:
  a=old['summaries'][c][g];b=new['summaries'][c][g]
  metrics=[f"{fmt(a['metrics'][k]['median_reduction_pct'])}→{fmt(b['metrics'][k]['median_reduction_pct'])}" for k,_ in keys]
  lines.append(f"| {labels[c]} | {g} | {' | '.join(metrics)} | {a['false_stop_count']}→{b['false_stop_count']} | {a['yaw_rate_max_deg_s']:.3f}→{b['yaw_rate_max_deg_s']:.3f} |")
lines.extend(['','## 各路径 G1/G2L 实测速率中位/最大与触发偏航误差中位','', '| 路径 | 组 | 原 D 最大速率 (°/s) | 新中位/最大速率 (°/s) | 旧/新触发偏航误差中位 (°) |','|---|---|---:|---:|---:|'])
for c in paths:
 for g in ('G1','G2L'):
  b=new['summaries'][c][g];a=old['summaries'][c][g];err=b.get('yaw_error_at_trigger_median_deg')
  lines.append(f"| {labels[c]} | {g} | {a['yaw_rate_max_deg_s']:.3f} | {b['yaw_rate_median_deg_s']:.3f}/{b['yaw_rate_max_deg_s']:.3f} | —/{err:.3f} |" if err is not None else f"| {labels[c]} | {g} | {a['yaw_rate_max_deg_s']:.3f} | {b['yaw_rate_median_deg_s']:.3f}/{b['yaw_rate_max_deg_s']:.3f} | —/— |")
lines.extend(['', '旧 D 原时程不可回读，旧速率中位和触发时刻偏航误差不在旧 JSON；— 表示不可核，非零。新触发偏航误差读取本轮小表，G1 无停机触发时采用同一路径预定触发时刻，具体时间定义见生成脚本。','', '## 超速例外：修订2事后决定', '', f"{len(new['rate_exceptions'])} 次 S3_30 超限；全 396 次限速判据不通过。以下 (a)(b)(c) 是 Lead 看过风暴初算后允许的条件性重判，不可表述为修复全通过。", '', '| 路径 | 种子 | 规则 | 最大1s割线 (°/s) |','|---|---:|---|---:|'])
for x in new['rate_exceptions']:lines.append(f"| {labels[x['case']]} | {x['seed']} | {x['group']} | {x['deg_s']:.5f} |")
lines.extend(['','## 原判据 (a)(b)(c)','', '| 路径 | (a) G2L 力矩降幅 ≥10% | (b) 负向载荷恶化均 ≤10% | (c) 达 G2L 80% 的简单规则误停均 > G2L | 旧→新 |', '|---|---|---|---|---|'])
for c in paths:
 a=old['gates'][c];b=new['gates'][c]
 lines.append(f"| {labels[c]} | {'是' if b['a'] else '否'} | {'是' if b['b'] else '否'} | {'不判' if b['c'] is None else ('是' if b['c'] else '否')}（{','.join(b['qualifying_simple']) or '无'}；G2L {new['false_stop_total']['G2L']}/36） | {'是' if a['passes'] else '否'}→{'不判' if b['passes'] is None else ('是' if b['passes'] else '否')} |")
lines.extend(['','负向载荷规则：任一路径 (b) 不成立即按原判据判否；即便三路径均通过，也只限这套配置/解析入流。LOS 为移动解析均值＋固定残差近似；触发离线重放。旧 D 的 I_near s112 G1 0.813°/s 与重跑高精度同链 0.308°/s 不一致，旧时程不可回读，原因未能在旧文件上定点定位。', '','稳态误停分均速原→新：'])
for m in ('18','20','22'):
 lines.append(f"{m} m/s："+'；'.join(f"{g} {old['false_stop_by_mean'][m][g]}→{new['false_stop_by_mean'][m][g]}" for g in rules))
lines.extend(['',f"稳态限速超限：{len(new.get('stationary_rate_exceptions',[]))}/36；" + (', '.join(str(x) for x in new.get('stationary_rate_exceptions',[])) if new.get('stationary_rate_exceptions') else '无')])
out.write_text('\n'.join(lines))
print(out, 'lines',len(lines),'rate',max([new['stationary_yaw_max_deg_s']]+[new['gates'][c]['yaw_rate_max_deg_s'] for c in paths]))
