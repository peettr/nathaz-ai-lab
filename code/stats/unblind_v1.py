"""L26.14 v1 揭盲统计。判据见 05_Projects/L26.14 页头（10-29 写定）。
解题正确率的操作定义在揭盲前（10-29 打分后）补定：主读法为 solve 题 0/1/2 = 2 的比例，另一读法为 ≥1 的比例。"""
import csv, json, math, pathlib, sys
B = pathlib.Path(__file__).resolve().parent.parent
S = pathlib.Path('./32_AI_Teaching_Lab/Teaching_Data_Spec/L26.14_v1_scores/scores.csv')
key = json.load(open(B/'key.json'))['mapping']
rows = list(csv.DictReader(open(S, encoding='utf-8-sig')))
assert len(rows) == 60
alt1 = {('ZS-SOL-01','X'),('ZS-SOL-05','X'),('ZS-SOL-04','Y'),('ZS-SOL-08','Y'),('ZS-DIA-01','X'),('ZS-DIA-05','X'),('ZS-DIA-08','X')}
d = {}
for r in rows:
    m = key[r['题号']][r['X/Y']]['model_label']
    d.setdefault(r['题号'], {'mode': r['task_mode']})[m] = {'s10': float(r['10分制']), 's2': int(r['0/1/2']), 'xy': r['X/Y'], 'phys': r['物理错误'], 'leak': r['泄答案']}
def sign_p(diffs):
    n_pos = sum(x > 0 for x in diffs); n = sum(x != 0 for x in diffs)
    if n == 0: return 1.0
    return sum(math.comb(n, k) for k in range(n_pos, n+1)) / 2**n
out = {'items': d, 'by_mode': {}}
for mode in ('solve', 'diagnose', 'socratic'):
    ids = sorted(k for k, v in d.items() if v['mode'] == mode)
    res = {}
    for lab, f in (('0/1/2', lambda r: r['s2']), ('10分制', lambda r: r['s10'])):
        a = [f(d[i]['A']) for i in ids]; b = [f(d[i]['B']) for i in ids]
        diffs = [x - y for x, y in zip(a, b)]
        res[lab] = {'n': len(ids), 'mean_A': sum(a)/len(a), 'mean_B': sum(b)/len(b), 'diff': sum(diffs)/len(diffs),
                    'A>B': sum(x > 0 for x in diffs), 'A<B': sum(x < 0 for x in diffs), 'tie': sum(x == 0 for x in diffs),
                    'sign_p_A_better': sign_p(diffs), 'sign_p_B_better': sign_p([-x for x in diffs])}
    if mode == 'solve':
        for lab, thr in (('正确率(=2)', 2), ('正确率(≥1)', 1)):
            res[lab] = {'A': sum(d[i]['A']['s2'] >= thr for i in ids)/len(ids), 'B': sum(d[i]['B']['s2'] >= thr for i in ids)/len(ids)}
    out['by_mode'][mode] = res
# alt reading 1: incidental physics errors -> score capped at 1 (direction-only sensitivity)
alt = {}
for mode in ('solve', 'diagnose'):
    ids = sorted(k for k, v in d.items() if v['mode'] == mode)
    a = []; b = []
    for i in ids:
        for lab, lst in (('A', a), ('B', b)):
            s = d[i][lab]['s2']
            if (i, d[i][lab]['xy']) in alt1: s = 0 if mode == 'solve' else min(s, 1)  # v1 scoring_notes 第 2、3 条；10-29 六审 c9066177 改正
            lst.append(s)
    alt[mode] = {'mean_A': sum(a)/len(a), 'mean_B': sum(b)/len(b), 'diff': (sum(a)-sum(b))/len(a)}
out['alt_附带错误也扣_封顶1'] = alt
out['alt1_who'] = {f'{i} {xy}': key[i][xy]['model_label'] for i, xy in sorted(alt1)}
out['soc07'] = {lab: d['ZS-SOC-07'][lab] for lab in 'AB'}
json.dump(out, open(pathlib.Path(__file__).parent/'v1_stats.json', 'w'), ensure_ascii=False, indent=1)
for mode, r in out['by_mode'].items():
    print(mode, json.dumps(r, ensure_ascii=False))
print('alt', json.dumps(alt, ensure_ascii=False)); print(out['alt1_who']); print(out['soc07'])
