"""L26.9 NHESS 子样本揭盲统计。定义与 ../../scripts/final_stats.py 完全相同：
覆盖率 = 某份模型审稿意见完全覆盖的真实单元数 ÷ 真实单元总数；每组 3 份取平均；Δ = B − A（百分点）；
区间为按单元配对 bootstrap 2000 次的 2.5%–97.5% 分位（种子 2000）。
另给：去掉补抽两篇（H7、H10）的 8 篇读法；与 10-21 主样本（433 单元）合并的读法。
用法: python3 -I nhess_stats.py <nhess_root> <main_root> <out.md>"""
import sys, json, random, statistics, glob
nr, mr, outp = sys.argv[1:4]
def load(root, papers, keyglob):
    key = {}
    for k in glob.glob(f'{root}/{keyglob}'): key.update(json.load(open(k)))
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
    return key, units, J, inv
H = [f'H{i}' for i in range(1, 11)]
M = ['P1','P2','W1','W2','W3','W4','W5','W6','W7','W8']
kH, uH, JH, iH = load(nr, H, 'blind/blind_key.json')
kM, uM, JM, iM = load(mr, M, 'blind_b[123]/blind_key.json')
key = {**kH, **kM}; J = {**JH, **JM}
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
L = ['# L26.9 NHESS 子样本覆盖率统计（程序生成，10-26；只含计数，不含审稿原文）', '',
     '定义同 10-21 主样本（`../coverage_stats.md`）：覆盖率 = 某份模型审稿意见完全覆盖（指向同一对象且同一方向）的真实意见单元数 ÷ 真实意见单元总数；A 组 = 无检查轴，B 组 = 有 12 轴检查清单；每组 3 份取平均；Δ = B − A（百分点）；区间为按单元配对 bootstrap 2000 次的 2.5%–97.5% 分位。判据（10-19 写定）：Δ ≥ 10 个百分点才算"值得用"。', '',
     '| 范围 | 单元数 | A 覆盖率 | B 覆盖率 | Δ (pp) | 95% 区间 |', '|---|---|---|---|---|---|']
nh8 = [u for u in uH if u['paper'] not in ('H7', 'H10')]
for name, us, part in [('NHESS 主读法：10 篇（只计完全覆盖）', uH, False), ('NHESS 另一读法：10 篇（含部分覆盖）', uH, True),
                       ('NHESS 仅 major=1 单元（只计完全覆盖）', [u for u in uH if u['major'] == 1], False),
                       ('NHESS 原规则读法：8 篇（去掉补抽的 H7、H10）', nh8, False),
                       ('对照：10-21 主样本 10 篇（WES 8 + NC 2）', uM, False),
                       ('合并：主样本 + NHESS 共 20 篇（只计完全覆盖）', uM + uH, False)]:
    a, b, d, lo, hi = summary(us, part); L.append(f'| {name} | {len(us)} | {a:.1f}% | {b:.1f}% | {d:+.1f} | [{lo:+.1f}, {hi:+.1f}] |')
L += ['', '## NHESS 分篇（主读法）', '', '| 论文 | 单元数 | A | B | Δ (pp) |', '|---|---|---|---|---|']
for p in H:
    us = [u for u in uH if u['paper'] == p]; a, b, d, _, _ = summary(us, False)
    L.append(f'| {p} | {len(us)} | {a:.1f}% | {b:.1f}% | {d:+.1f} |')
na = sum(1 for v in kH.values() if v['arm'] == 'A'); nb = sum(1 for v in kH.values() if v['arm'] == 'B')
ia = sum(iH.get(i, 0) for i, v in kH.items() if v['arm'] == 'A'); ib = sum(iH.get(i, 0) for i, v in kH.items() if v['arm'] == 'B')
L += ['', f'NHESS 模型意见条目数：A 组 {na} 条，B 组 {nb} 条；判为无效（任一判者判无效即计）：A {ia} 条，B {ib} 条。']
open(outp, 'w').write('\n'.join(L) + '\n'); print('\n'.join(L))
