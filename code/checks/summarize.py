"""Build L26.10 results table from results/J0..J3 with the frozen L1 checker. Output: results/汇总表.md + summary.json"""
import json, sys
from pathlib import Path
B = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(B / 'checks'))
from l1_check import check
runs = {}
for j in ('J0', 'J1', 'J2', 'J3'):
    for d in sorted((B / 'results' / j).iterdir()):
        if d.is_dir():
            runs[d.name] = d
def kind(n): return 'B' if n.startswith(('B_', 'M3', 'M4')) else 'A'
res = {n: check(d, kind(n)) for n, d in runs.items()}
secs = {n: json.loads((d / 'time.json').read_text())['seconds'] for n, d in runs.items()}
cd = {n: r['cd_mean_last20'] for n, r in res.items()}
cleanA = [cd[f'A_clean_{i}'] for i in range(1, 6)]; cleanB = [cd[f'B_clean_{i}'] for i in range(1, 6)]
rngA, rngB = max(cleanA) - min(cleanA), max(cleanB) - min(cleanB)
inj = [n for n in res if n.startswith('M')]
rb = [n for n in res if n.startswith('Rb')]
def base(n): return (sum(cleanB) / 5) if kind(n) == 'B' else (sum(cleanA) / 5)
def rng(n): return rngB if kind(n) == 'B' else rngA
rows, c3 = [], []
for n in sorted(inj):
    r = res[n]; shift = None if cd[n] is None else cd[n] - base(n)
    # effect exists: L1 readback/mesh check differs from task spec (all K01/K02/K09 fails) or C_D shift > 3*range
    spec_fail = [k for k in r['l1_failed'] if k.startswith(('K01', 'K02', 'K09'))]
    changed = shift is not None and abs(shift) > 3 * rng(n)
    effective = bool(spec_fail) or changed or r['l0'] == 'block'
    rows.append((n, r['l0'], r['l1'], r['l2'], cd[n], shift, effective, ','.join(r['l1_failed'])))
    if n.endswith('_fine') and shift is not None and changed:
        c3.append((n, abs(shift), rng(n), rng(n) < abs(shift) / 2))
eff = [x for x in rows if x[6]]
auto = sum(1 for x in rows if x[1] in ('pass', 'block') and x[2] in ('pass', 'block'))
core_h = sum(secs.values()) / 3600
fa_A = sum(1 for i in range(1, 6) if 'block' in (res[f'A_clean_{i}']['l0'], res[f'A_clean_{i}']['l1'], res[f'A_clean_{i}']['l2']))
fa_B = sum(1 for i in range(1, 6) if 'block' in (res[f'B_clean_{i}']['l0'], res[f'B_clean_{i}']['l1'], res[f'B_clean_{i}']['l2']))
miss = {L: [x[0] for x in eff if x[{'L0': 1, 'L1': 2, 'L2': 3}[L]] == 'pass'] for L in ('L0', 'L1', 'L2')}
C1 = auto / len(rows) >= 0.9 and core_h <= 6
k10 = 'K10 PASS' in (B / 'checks' / 'K10_selftest_result.txt').read_text()
C2 = fa_A <= 1 and fa_B <= 1 and k10
C3 = len(c3) > 0 and sum(1 for x in c3 if x[3]) >= len(c3) / 2
S = {'n_runs': len(res), 'core_hours': core_h, 'C1': {'auto': f'{auto}/{len(rows)}', 'core_h': round(core_h, 3), 'ok': C1},
     'C2': {'false_alarm_A': fa_A, 'false_alarm_B': fa_B, 'K10': k10, 'ok': C2},
     'C3': {'items': c3, 'range_A': rngA, 'range_B': rngB, 'ok': C3},
     'effective': len(eff), 'missed': {k: v for k, v in miss.items()},
     'Rb': {n: {'l0': res[n]['l0'], 'l1': res[n]['l1'], 'cd': cd[n], 'l0_detail': [x[:160] for x in res[n]['l0_detail']]} for n in rb}}
(B / 'results' / 'summary.json').write_text(json.dumps(S, ensure_ascii=False, indent=1, default=str))
L = ['# L26.10 拦截汇总表（checks/summarize.py 程序生成；L1 用冻结版 l1_check.py）', '',
     f'运行 {len(res)} 个，计算合计 {core_h:.2f} 核·时。干净基线 A 5 次 C_D = {sorted(set(cleanA))}（极差 {rngA:g}）；B 5 次 C_D = {sorted(set(cleanB))}（极差 {rngB:g}）。', '',
     '| 注入 | L0 T28 闸门 | L1 清单脚本 | L2 C_D∈[1,3] | C_D 末20步 | 相对干净偏移 | 有效注入 | L1 未过项 |', '|---|---|---|---|---|---|---|---|']
for n, l0, l1, l2, c, s, e, f in rows:
    L.append(f"| {n} | {'拦下' if l0=='block' else '**放行**'} | {'拦下' if l1=='block' else '**放行**'} | {'拦下' if l2=='block' else '放行'} | {'—' if c is None else f'{c:.6g}'} | {'—' if s is None else f'{s:+.3g}'} | {'是' if e else '否'} | {f} |")
L += ['', f"- 有效注入 {len(eff)}/{len(rows)}；漏拦：L0 {len(miss['L0'])} 个 {miss['L0']}；L1 {len(miss['L1'])} 个；L2 {len(miss['L2'])} 个。",
      f"- C1：自动判定 {auto}/{len(rows)}，计算 {core_h:.2f} 核·时 ≤ 6 → {'成立' if C1 else '不成立'}",
      f"- C2：误报 A {fa_A}/5、B {fa_B}/5，K10 {'PASS' if k10 else 'FAIL'} → {'成立' if C2 else '不成立'}",
      f"- C3：有效细档 {len(c3)} 类，满足 极差 < |偏移|/2 的 {sum(1 for x in c3 if x[3])} 类 → {'成立' if C3 else '不成立'}（极差 A {rngA:g}、B {rngB:g}）", '',
      '## R-b（bot 从零生成 5 份设置）', '| 运行 | L0 | L1 | C_D | L0 抛错（截断） |', '|---|---|---|---|---|']
for n in rb:
    L.append(f"| {n} | {res[n]['l0']} | {res[n]['l1']} | {cd[n]!r} | {'; '.join(x[:110] for x in res[n]['l0_detail'])} |")
(B / 'results' / '汇总表.md').write_text('\n'.join(L) + '\n')
print('\n'.join(L))
