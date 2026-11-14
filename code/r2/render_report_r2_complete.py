"""Non-destructive completed table from the already pulled JSON reductions."""
import hashlib
import json
import statistics
from pathlib import Path

p = Path(__file__).resolve().parent
root = p.parent.parent
new = json.loads((p / 'metrics_D_yawfix.json').read_text())
old = json.loads((root / 'metrics_D.json').read_text())
assert new['completed_storm'] == old['completed_storm'] == 360
assert new['completed_stationary'] == old['completed_stationary'] == 36
cases = ('I_near', 'III_kzm05', 'III_kzm00')
labels = ('Case I', 'Case III kzm=.05', 'Case III kzm=0')
keys = ('tower_top_yaw_absmax_kNm', 'tower_fore_aft_negative_magnitude_kNm', 'blade_root_negative_magnitude_kNm')
lines = ['# 分段 D 偏航限速 r2 完整重判表（修订2，非破坏性补表）', '',
         '此表由 metrics_D_yawfix.json 与旧 metrics_D.json 自动生成；原 RESULTS_D_yawfix.md/metrics_D_yawfix.json 原样保留。',
         '', '风暴 360/360、稳态 36/36；稳态最大高精度 ES NacYaw 1 s 割线 0.290301°/s、超限 0/36。'
         ' 风暴超限 16/360，均 S3_30（最高 0.350484°/s），故原“全运行限速已修”不成立。'
         ' 修订2是看过初算后的事后例外，仅允许条件性重判。',
         '稳态 *_rules.json 的 yaw_max_rate_deg_s 是 np.gradient 瞬时值（最大约 0.478°/s，含弹性振动），不用于 1 s 割线限速判定。',
         '', '## G2L 与 G1 配对中位降幅；原 D 对照', '',
         '| 路径 | G2L 偏航峰降幅（旧→新） | 塔底前后负峰（旧→新） | 三叶根面外负峰（旧→新） | 新 Wilcoxon p（偏航/塔/叶） | (a,b,c) 旧→新 |',
         '|---|---:|---:|---:|---|---|']
for c, label in zip(cases, labels):
    a, b = old['summaries'][c]['G2L'], new['summaries'][c]['G2L']
    rates = [f"{a['metrics'][k]['median_reduction_pct']:+.2f}%→{b['metrics'][k]['median_reduction_pct']:+.2f}%" for k in keys]
    ps = '/'.join(f"{b['metrics'][k]['wilcoxon_p']:.5g}" if b['metrics'][k]['wilcoxon_p'] is not None else '—' for k in keys)
    ga, gb = old['gates'][c], new['gates'][c]
    tri = lambda g: '/'.join('不判' if g[k] is None else ('是' if g[k] else '否') for k in ('a', 'b', 'c'))
    lines.append(f"| {label} | {' | '.join(rates)} | {ps} | {tri(ga)}→{tri(gb)} |")
lines += ['', '注：负降幅为恶化；Wilcoxon 双侧配对 p 值，探索性、未多重校正。',
          '', '## 全部规则：偏航降幅、稳态误停与 1 s 割线速率', '',
          '| 路径 | 组 | 偏航降幅旧→新 (%) | 误停旧→新 /36 | 旧速率中位/最大 | 新速率中位/最大 (°/s) | 新超限/12 | 新触发偏航误差中位 (°) |',
          '|---|---|---:|---:|---:|---:|---:|---:|']
for c, label in zip(cases, labels):
    for g in new['rules']:
        a, b = old['summaries'][c][g], new['summaries'][c][g]
        oldrates = [r['yaw_rate_max_deg_s'] for r in old['records'][c] if r['group'] == g]
        assert len(oldrates) == 12
        nr = [r['yaw_rate_max_deg_s'] for r in new['records'][c] if r['group'] == g]
        assert len(nr) == 12
        error = b.get('yaw_error_at_trigger_median_deg')
        lines.append(f"| {label} | {g} | {a['metrics'][keys[0]]['median_reduction_pct']:+.2f}→{b['metrics'][keys[0]]['median_reduction_pct']:+.2f} | {a['false_stop_count']}→{b['false_stop_count']} | {statistics.median(oldrates):.3f}/{max(oldrates):.3f} | {statistics.median(nr):.3f}/{max(nr):.3f} | {sum(x > .31 for x in nr)} | {error:.3f} |" if error is not None else
                     f"| {label} | {g} | {a['metrics'][keys[0]]['median_reduction_pct']:+.2f}→{b['metrics'][keys[0]]['median_reduction_pct']:+.2f} | {a['false_stop_count']}→{b['false_stop_count']} | {statistics.median(oldrates):.3f}/{max(oldrates):.3f} | {statistics.median(nr):.3f}/{max(nr):.3f} | {sum(x > .31 for x in nr)} | — |")
lines += ['', '旧速率来自低精度 ASCII 派生 JSON；旧 I_near s112 G1 0.813°/s 与高精度同链重跑不一致，旧原始时程不可回读。旧触发偏航误差无原始时程，不能并列重建；“—”非零。'
          '新 G1 无停机触发，所列为同一路径预定触发时刻的偏航误差（另见 trigger_yaw_error_r2.json），并非 G1 实际停机触发。',
          '', '## 判据与适用性', '']
for c, label in zip(cases, labels):
    gate = new['gates'][c]
    lines.append(f"{label}：(a) {'是' if gate['a'] else '否'}；(b) {'是' if gate['b'] else '否'}；(c) {'不判' if gate['c'] is None else ('是' if gate['c'] else '否')}，达 80% 的简单规则 {','.join(gate['qualifying_simple']) or '无'}，G2L 误停 {new['false_stop_total']['G2L']}/36。")
lines += ['任一路径 (b) 不成立即原规则判否；S3_30 若进入 (c) 比较则该项“不判”。当前三路径的 S3_30 均未进入 (c)，但其 16 次限速超标不可抹去。',
          'LOS 是移动解析均值＋固定残差近似，触发为离线重放；本表是条件性计算，不是全运行偏航限速验收通过。',
          '', '## 起止、CU 与来源',
          'Colab CPU Standard 会话 a3-d-yawfix-r2-1108：2026-11-08 00:53:53–15:18:04 美东（用户请求 stop）；稳态段 12:57:49–15:13:03 美东。0 SU。'
          '本会话实测 CU 无单会话账单，无法归因；若 0.5 CU/h 适用于全部约 14.4033 h 分配时间，条件估算约 7.20 CU，超过 4 CU 上限，不能当作账单。',
          'keepalive state=done、final_pull_state=ok；私有 colab_state.json 为空。', '']
for name in ('analyze_d_r2_revision2.py', 'render_report_r2_revision2.py', 'render_report_r2_complete.py'):
    lines.append(f"{name} SHA256 {hashlib.sha256((p / name).read_bytes()).hexdigest()}")
lines.append('')
out = p / 'RESULTS_D_yawfix_complete_r2.md'
assert not out.exists(), 'Existing report is immutable; use a new version name'
out.write_text('\n'.join(lines))
print(out, len(lines), 'lines')
