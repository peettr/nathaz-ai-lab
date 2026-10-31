"""L26.14 v2 揭盲统计 + 与 v1 合并。判据见 05_Projects/L26.14 页头（10-29 写定，主口径按 v2）。
解题正确率：主读法 = solve 项 0/1/2 为 2 的比例；另一读法 = ≥1 的比例（打分后、揭盲前补定）。"""
import csv, json, math, pathlib
B = pathlib.Path(__file__).resolve().parent.parent
S = pathlib.Path('./32_AI_Teaching_Lab/Teaching_Data_Spec/L26.14_v2_scores/scores.csv')
key = json.load(open(B/'v2'/'key.json'))['pairs']
rows = list(csv.DictReader(open(S, encoding='utf-8-sig')))
assert len(rows) == 120
lab = {'OpenDCAI/Omni-Edu-9B': 'A', 'Qwen/Qwen3.5-9B': 'B'}
d = {}
for r in rows:
    m = lab[key[f"{r['题号']}::{r['task_mode']}"][r['X/Y']]]
    d.setdefault((r['题号'], r['task_mode']), {})[m] = {'s': int(r['0/1/2']), 'xy': r['X/Y'], 'phys': r['物理错误'], 'leak': r['泄答案'], 'trunc': r['截断']}
assert all(len(v) == 2 for v in d.values()) and len(d) == 60
# 截断核对
ansB = {(x['id'], x['task_mode']): x for x in map(json.loads, open(B/'v2'/'answers_B.jsonl'))}
ansA = {(x['id'], x['task_mode']): x for x in map(json.loads, open(B/'v2'/'answers_A.jsonl'))}
trunc_check = {f'{k[0]}::{k[1]}': {m: (ansA if m == 'A' else ansB)[k]['truncated'] for m in 'AB'} for k in d if any(d[k][m]['trunc'] == '是' for m in 'AB')}
def short(i): return i.replace('L26-', '')
# 另一读法（scoring_notes 7–10），按 题号短名+项+X/Y 指定
alts = {
 '7_陈述定义不算泄露(1→2)': ('socratic', ['DIA-07 X','DIA-01 X','DIA-01 Y','SOL-07 X','SOL-08 X','DIA-05 Y','DIA-08 Y','DIA-02 Y','DIA-03 Y','SOL-02 X','SOL-02 Y','SOL-03 X','SOL-03 Y','SOL-05 X','SOL-09 Y','SOL-10 Y'], lambda s: 2 if s == 1 else s),
 '8_外泄思考也算(0→1)': ('diagnose', ['DIA-05 Y'], lambda s: 1 if s == 0 else s),
 '9_按最终结论判(→2)': ('diagnose', ['SOL-09 X', 'SOL-10 Y'], lambda s: 2),
 '10_不自洽记实质(→0)': ('solve', ['SOL-08 X', 'DIA-05 X'], lambda s: 0),
}
def sign_p(df):
    n = sum(x != 0 for x in df); p = sum(x > 0 for x in df)
    return sum(math.comb(n, k) for k in range(p, n+1)) / 2**n if n else 1.0
def stats(dd, mode):
    ks = sorted(k for k in dd if k[1] == mode)
    a = [dd[k]['A']['s'] for k in ks]; b = [dd[k]['B']['s'] for k in ks]
    df = [x - y for x, y in zip(a, b)]
    r = {'n': len(ks), 'mean_A': round(sum(a)/len(a), 3), 'mean_B': round(sum(b)/len(b), 3), 'diff': round(sum(df)/len(df), 3),
         'A胜/负/平': f'{sum(x>0 for x in df)}/{sum(x<0 for x in df)}/{sum(x==0 for x in df)}',
         'p_A更好': round(sign_p(df), 4), 'p_B更好': round(sign_p([-x for x in df]), 4)}
    r['明显更好(A)'] = r['diff'] >= 0.3 and r['p_A更好'] < 0.1
    if mode == 'solve':
        r['正确率=2'] = {m: round(sum(dd[k][m]['s'] == 2 for k in ks)/len(ks), 3) for m in 'AB'}
        r['正确率≥1'] = {m: round(sum(dd[k][m]['s'] >= 1 for k in ks)/len(ks), 3) for m in 'AB'}
    return r
def verdict(st):
    good = st['diagnose']['明显更好(A)'] or st['socratic']['明显更好(A)']
    acc = st['solve']['正确率=2']; ok = acc['A'] >= acc['B'] - 0.05
    acc1 = st['solve']['正确率≥1']; ok1 = acc1['A'] >= acc1['B'] - 0.05
    return {'诊断或引导明显更好': good, '解题正确率不差>5pp(=2)': ok, '(≥1)': ok1, '判': '值得用' if good and ok else '放弃'}
out = {'trunc_check': trunc_check, 'main': {m: stats(d, m) for m in ('solve', 'diagnose', 'socratic')}}
out['main_verdict'] = verdict(out['main'])
out['alts'] = {}
import copy
for name, (mode, lst, f) in alts.items():
    dd = copy.deepcopy(d); hit = []
    for k in dd:
        if k[1] != mode: continue
        for m in 'AB':
            tag = f"{short(k[0])} {dd[k][m]['xy']}"
            if tag in lst:
                dd[k][m]['s'] = f(dd[k][m]['s']); hit.append(f'{tag}={m}')
    st = {m: stats(dd, m) for m in ('solve', 'diagnose', 'socratic')}
    out['alts'][name] = {'hits': hit, mode: st[mode], 'verdict': verdict(st)}
# 全部另一读法同时用
dd = copy.deepcopy(d)
for name, (mode, lst, f) in alts.items():
    for k in dd:
        if k[1] != mode: continue
        for m in 'AB':
            if f"{short(k[0])} {dd[k][m]['xy']}" in lst: dd[k][m]['s'] = f(dd[k][m]['s'])
st = {m: stats(dd, m) for m in ('solve', 'diagnose', 'socratic')}
out['alts']['全部另一读法'] = {'stats': st, 'verdict': verdict(st)}
# 与 v1 合并（敏感性；v2 由 v1 改写，题目有重叠，不当独立样本）
v1 = json.load(open(pathlib.Path(__file__).parent/'v1_stats.json'))['items']
comb = dict(d)
for i, v in v1.items():
    comb[('v1:'+i, v['mode'])] = {m: {'s': v[m]['s2']} for m in 'AB'}
st = {m: stats(comb, m) for m in ('solve', 'diagnose', 'socratic')}
out['v1+v2合并'] = {'stats': st, 'verdict': verdict(st)}
for m in 'AB':
    out.setdefault('counts', {})[m] = {'实质物理错误': sum(d[k][m]['phys'] == '实质' for k in d), '泄答案是': sum(d[k][m]['leak'] == '是' for k in d), '泄答案部分': sum(d[k][m]['leak'] == '部分' for k in d)}
json.dump(out, open(pathlib.Path(__file__).parent/'v2_stats.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
