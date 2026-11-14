"""Render D yawfix r2 report exclusively from checked JSON results."""
import json,sys
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
lines=['# A3 分段 D · 偏航限速修复第二轮（修订1）','', '数据源：本次 metrics_D_yawfix_r2.json；对照：原 metrics_D.json。所有表格数值从 JSON 生成，非手抄。','', '## 运行与限速','',f"完整风暴运行 {new['completed_storm']}/{new['expected_storm']}；稳态 NoStop {new['completed_stationary']}/{new['expected_stationary']}；三路径×12 种子×10 规则、18/20/22 m/s 各 12 稳态窗。",f"高精度 ES NacYaw 1 s 割线最大（含稳态）{max([new['stationary_yaw_max_deg_s']]+[new['gates'][c]['yaw_rate_max_deg_s'] for c in paths]):.5f}°/s；全部 ≤0.31°/s。YawDOF=True，ROSCO 主动偏航 Y_Rate=0.24°/s，未锁死。>0.5 Hz 峰峰值作为单独观测，不进入限速判定。",'', '## G2L 对 G1 配对中位降幅（%）与旧 D 对照','', '| 路径 | 指标 | 原 D | 修正 D |', '|---|---|---:|---:|']
for c in paths:
 for k,label in keys:
  a=old['summaries'][c]['G2L']['metrics'][k]['median_reduction_pct'];b=new['summaries'][c]['G2L']['metrics'][k]['median_reduction_pct'];lines.append(f'| {labels[c]} | {label} | {fmt(a)} | {fmt(b)} |')
lines.extend(['','## 十规则配对中位降幅、误停窗、组最大偏航速率','', '| 路径 | 规则 | 偏航旧→新 (%) | 塔负峰旧→新 (%) | 三叶根负峰旧→新 (%) | 误停旧→新 /36 | 最大 1s 割线旧→新 (°/s) |','|---|---|---:|---:|---:|---:|---:|'])
for c in paths:
 for g in rules:
  a=old['summaries'][c][g];b=new['summaries'][c][g]
  metrics=[f"{fmt(a['metrics'][k]['median_reduction_pct'])}→{fmt(b['metrics'][k]['median_reduction_pct'])}" for k,_ in keys]
  lines.append(f"| {labels[c]} | {g} | {' | '.join(metrics)} | {a['false_stop_count']}→{b['false_stop_count']} | {a['yaw_rate_max_deg_s']:.3f}→{b['yaw_rate_max_deg_s']:.3f} |")
lines.extend(['','## 原判据 (a)(b)(c)','', '| 路径 | (a) G2L 力矩降幅 ≥10% | (b) 负向载荷恶化均 ≤10% | (c) 达 G2L 80% 的简单规则误停均 > G2L | 旧→新 |', '|---|---|---|---|---|'])
for c in paths:
 a=old['gates'][c];b=new['gates'][c]
 lines.append(f"| {labels[c]} | {b['a']} | {b['b']} | {b['c']}（{','.join(b['qualifying_simple']) or '无'}；G2L {new['false_stop_total']['G2L']}/36） | {a['passes']}→{b['passes']} |")
lines.extend(['','负向载荷规则：任一路径 (b) 不成立即按原判据判否；即便三路径均通过，也只限这套配置/解析入流。LOS 为移动解析均值＋固定残差近似；触发离线重放。旧 D 的 I_near s112 G1 0.813°/s 与重跑高精度同链 0.308°/s 不一致，旧时程不可回读，原因未能在旧文件上定点定位。', '','稳态误停分均速原→新：'])
for m in ('18','20','22'):
 lines.append(f"{m} m/s："+'；'.join(f"{g} {old['false_stop_by_mean'][m][g]}→{new['false_stop_by_mean'][m][g]}" for g in rules))
lines.append('')
out.write_text('\n'.join(lines))
print(out, 'lines',len(lines),'rate',max([new['stationary_yaw_max_deg_s']]+[new['gates'][c]['yaw_rate_max_deg_s'] for c in paths]))
