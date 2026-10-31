"""L26.9 揭盲总统计（10 篇）。覆盖率定义：某组某份审稿意见覆盖的真实单元数 / 真实单元总数；每组 3 份取平均；
Δ = B 组覆盖率 − A 组覆盖率（百分点）。主读法只计完全覆盖；另一读法含部分覆盖。bootstrap 按单元配对重抽 2000 次。
用法: python3 -I final_stats.py <root> <out.md>"""
import sys, json, random, statistics, glob
root, outp = sys.argv[1], sys.argv[2]
key = {}
for k in glob.glob(f'{root}/blind_b[123]/blind_key.json'): key.update(json.load(open(k)))
papers = ['P1','P2','W1','W2','W3','W4','W5','W6','W7','W8']
units, J, inv = [], {}, {}
for p in papers:
    for l in open(f'{root}/units/{p}.jsonl'):
        u = json.loads(l)
        if not u.get('unplaceable'): units.append(u)
    for l in open(f'{root}/final/{p}_judgments.jsonl'):
        x = json.loads(l); J[x['unit_id']] = x
    for k in (1, 2):
        for l in open(f'{root}/judge/{p}_J{k}.jsonl'):
            x = json.loads(l)
            if x['type'] == 'item': inv[x['id']] = max(inv.get(x['id'], 0), x['invalid'])
def rate(u, arm, partial):
    ids = J[u['unit_id']]['covered_by'] + (J[u['unit_id']]['partial_by'] if partial else [])
    return sum(any(key[i]['arm'] == arm and key[i]['run'] == r for i in ids) for r in '123') / 3
def summary(us, partial):
    a = [rate(u, 'A', partial) for u in us]; b = [rate(u, 'B', partial) for u in us]
    d = [y - x for x, y in zip(a, b)]; rng = random.Random(2000); bs = []
    for _ in range(2000):
        s = [d[rng.randrange(len(d))] for _ in d]; bs.append(sum(s) / len(s))
    bs.sort()
    return 100*statistics.mean(a), 100*statistics.mean(b), 100*statistics.mean(d), 100*bs[49], 100*bs[1949]
L = ['# L26.9 覆盖率统计（程序生成，10-21；只含计数，不含审稿原文）', '',
     '定义：覆盖率 = 某份模型审稿意见完全覆盖（指向同一对象且同一方向）的真实意见单元数 ÷ 真实意见单元总数；A 组 = 无检查轴，B 组 = 有 12 轴检查清单；每组 3 份取平均；Δ = B − A（百分点）；区间为按单元配对 bootstrap 2000 次的 2.5%–97.5% 分位。', '',
     '| 范围 | 单元数 | A 覆盖率 | B 覆盖率 | Δ (pp) | 95% 区间 |', '|---|---|---|---|---|---|']
for name, us, part in [('主读法：10 篇合计（只计完全覆盖）', units, False), ('另一读法：10 篇合计（含部分覆盖）', units, True),
                       ('仅 major=1 单元（只计完全覆盖）', [u for u in units if u['major'] == 1], False)]:
    a, b, d, lo, hi = summary(us, part); L.append(f'| {name} | {len(us)} | {a:.1f}% | {b:.1f}% | {d:+.1f} | [{lo:+.1f}, {hi:+.1f}] |')
L += ['', '## 分篇（主读法）', '', '| 论文 | 单元数 | A | B | Δ (pp) |', '|---|---|---|---|---|']
for p in papers:
    us = [u for u in units if u['paper'] == p]; a, b, d, _, _ = summary(us, False)
    L.append(f'| {p} | {len(us)} | {a:.1f}% | {b:.1f}% | {d:+.1f} |')
na = sum(1 for i, v in key.items() if v['arm'] == 'A'); nb = sum(1 for i, v in key.items() if v['arm'] == 'B')
ia = sum(inv.get(i, 0) for i, v in key.items() if v['arm'] == 'A'); ib = sum(inv.get(i, 0) for i, v in key.items() if v['arm'] == 'B')
L += ['', f'模型意见条目数：A 组 {na} 条，B 组 {nb} 条；判为无效（事实错、与本文无关或不适用，任一判者判无效即计）：A {ia} 条，B {ib} 条。']
open(outp, 'w').write('\n'.join(L) + '\n'); print('\n'.join(L))
