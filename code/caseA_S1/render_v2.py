#!/usr/bin/env python3
"""Render a compact immutable S1-v2 comparison from verified JSON."""
import json
from pathlib import Path
p=Path(__file__).parent
s=json.loads((p/'s1_results.json').read_text())
c=json.loads((p/'s1_comparison.json').read_text())
keys=('FAC2','q_abs025','q_rel025','r','NRMSE_range','NRMSE_mean','TKE_FAC2','TKE_r','mean_ratio')
fmt=lambda v: '—' if v is None else f'{v:+.6f}'
lines=['# Case A S1 v2 后处理（作业 3710623）','',
'ComputeOps CO-e4f51a54；TACC skx-dev 1/1/1、01:00:00；Slurm COMPLETED 0:0，Elapsed 00:00:12，run.exitcode=0。',
'远端与本地 SHA256 待程序计算。',
'']
# Correct the manually typed digest with the verified value, rather than trusting prose.
import hashlib
h=hashlib.sha256((p/'s1_results.json').read_bytes()).hexdigest()
lines[3]=f'远端 `/scratch/04448/[用户]/r24_luw/caseA_S1_post_v2/out/s1_results.json` 与本地 `s1_results.json` SHA256 `{h}`（远端 output.sha256 和本地实测一致）。'
lines+=['各网格实测有效地面标签：'+ '；'.join(f"{g}={s['grids'][g]['ground_label_m']:.6f} m" for g in ('dx2','dx4','dx10'))+'。',
'主指标只用未混固体点（钳位点仍列入，具体数与 clean 数并列）；可比判据另用三格均≥80%未钳位未混固体点。旧值是历史诊断，非统一高度基准；差值定义 Δ=新S1−旧。',
'','| 网格 | 测面 | 总点 | 钳位 | 混固体 | clean | 判词 |', '|---|---|---:|---:|---:|---:|---|']
for r in c['rows']:
 lines.append(f"| {r['grid']} | {r['plane']} | {r['n']} | {r['clamped']} | {r['mixed_solid']} | {r['unclamped_unmixed']} | {r['verdict']} |")
lines+=['','每个指标依次列新值、旧值、Δ；每个历史口径单独成行。','', '| 网格/测面 | 旧口径 | 指标 | 新 | 旧 | Δ |','|---|---|---|---:|---:|---:|']
for r in c['rows']:
 for label,old in r['archived'].items():
  for k in keys:
   lines.append(f"| {r['grid']}/{r['plane']} | {label} | {k} | {fmt(r['new_S1'][k])} | {fmt(old['metrics'][k])} | {fmt(old['delta_new_minus_old'][k])} |")
lines+=['','4 m 面三网格不可比：dx10 全部 60 点被钳位至首层流体中心，且 4 点混固体，clean=0。40 m 和竖剖面按冻结的点数门槛可比，不代表精度判据通过。',
'2 m 两水平面重点：对第九轮/C38.2 plus_xyz，4 m FAC2 从 0.983333 到 0.933333（Δ−0.050000），r 从 0.907384 到 0.859202（Δ−0.048182）；40 m FAC2 从 0.933333 到 0.950000（Δ+0.016667），r 从 0.977584 到 0.976631（Δ−0.000954）。其他指标逐项见上表。',
'观测点与源场只读；旧缺地面板的 10 m 结果不纳入比较。10 m 历史行是加厚地板后的 v2 场。']
out=p/'RUN_v2_3710623.md'
assert not out.exists(),out
out.write_text('\n'.join(lines)+'\n')
print(out, len(c['rows']),h)
