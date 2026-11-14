"""只读诊断：从已有 Fluent 运行日志读出设置、边界和逐时间步收敛情况（T28，10-21）。

不连接 Fluent、不改任何文件，只读日志并输出 JSON 摘要：
- settings：日志里的 *_READBACK / REFERENCE / INLET / SOURCE_MODEL 行（看设置、查边界）；
- per_step：每个时间步的内迭代数、是否用满上限、各方程首末残差、连续性残差下降的数量级；
- summary：未收敛步数（末残差 > 判据）、用满上限的步数、连续性下降 <3 个数量级的步数占比。

用法：python diag_readonly.py <log> [--max-iter 50] [--criterion 1e-5] [--out diag.json]
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

ROW = re.compile(r'^\s*(\d+)\s+((?:[0-9.]+e[+-]\d+\s+)+)')
HEAD = re.compile(r'^\s*iter\s+(.*?)\s+time/iter')
KV = re.compile(r'^([A-Z_]+(?:READBACK)?|REFERENCE|INLET|SOURCE_MODEL|FLOW_TIME_START)\s+(.*)$')


def parse(path: Path, max_iter: int, crit: float):
    settings = {}
    cols = None
    steps, cur, last_iter = [], [], None
    for line in path.open(encoding='utf-8', errors='replace'):
        m = KV.match(line)
        if m and (m.group(1).endswith('READBACK') or m.group(1) in ('REFERENCE', 'INLET', 'SOURCE_MODEL', 'FLOW_TIME_START')):
            settings.setdefault(m.group(1), []).append(m.group(2).strip()[:400])
            continue
        h = HEAD.match(line)
        if h:
            cols = h.group(1).split()
            continue
        if line.startswith('Updating solution at time levels'):
            if cur:
                steps.append(cur)
            cur = []
            continue
        r = ROW.match(line)
        if r and cols:
            it = int(r.group(1))
            vals = [float(x) for x in r.group(2).split()[:len(cols)]]
            if it == last_iter:  # 新时间步第一行会重复打印上一迭代
                continue
            last_iter = it
            cur.append(dict(zip(cols, vals)))
    if cur:
        steps.append(cur)
    per = []
    for k, s in enumerate(steps):
        if len(s) < 2:
            continue
        first, last = s[0], s[-1]
        cont0, cont1 = first.get('continuity'), last.get('continuity')
        drop = math.log10(cont0 / cont1) if cont0 and cont1 else None
        per.append({'step': k, 'inner_iters': len(s), 'hit_max': len(s) >= max_iter,
                    'final_max_residual': max(last.values()),
                    'continuity_first': cont0, 'continuity_last': cont1,
                    'continuity_drop_orders': round(drop, 2) if drop is not None else None})
    n = len(per)
    summ = {
        'steps': n,
        'not_converged_final_gt_criterion': sum(p['final_max_residual'] > crit for p in per),
        'hit_max_iter': sum(p['hit_max'] for p in per),
        'continuity_drop_lt_3_orders': sum((p['continuity_drop_orders'] or 0) < 3 for p in per),
        'continuity_drop_median': sorted(p['continuity_drop_orders'] or 0 for p in per)[n // 2] if n else None,
        'max_iter_assumed': max_iter, 'criterion': crit,
    }
    if n:
        summ['continuity_drop_lt_3_orders_frac'] = round(summ['continuity_drop_lt_3_orders'] / n, 3)
    return {'log': str(path), 'settings': settings, 'summary': summ, 'per_step_head': per[:5]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--max-iter', type=int, default=50)
    ap.add_argument('--criterion', type=float, default=1e-5)
    ap.add_argument('--out')
    a = ap.parse_args()
    res = parse(Path(a.log), a.max_iter, a.criterion)
    txt = json.dumps(res, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).write_text(txt, encoding='utf-8')
    print(json.dumps(res['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
