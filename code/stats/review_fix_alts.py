"""六审 c9066177 后补算：①v2 逐题难判 4 条另一读法；②v2 套 v1 第 1 条（附带物理错误记实质：solve→0、diagnose 封顶 1、socratic→0）；③v1 第 1 条按原规则（solve→0、diagnose 封顶 1）；④v2 第 7 条读法的 bootstrap；⑤配对 t 上界。"""
import csv, json, math, random, pathlib, statistics as st
B = pathlib.Path(__file__).resolve().parent.parent
lab = {'OpenDCAI/Omni-Edu-9B': 'A', 'Qwen/Qwen3.5-9B': 'B'}
key2 = json.load(open(B/'v2'/'key.json'))['pairs']
rows2 = list(csv.DictReader(open('./32_AI_Teaching_Lab/Teaching_Data_Spec/L26.14_v2_scores/scores.csv', encoding='utf-8-sig')))
d2 = {}
for r in rows2:
    m = lab[key2[f"{r['题号']}::{r['task_mode']}"][r['X/Y']]]
    d2.setdefault((r['题号'].replace('L26-', ''), r['task_mode']), {})[m] = {'s': int(r['0/1/2']), 'xy': r['X/Y'], 'phys': r['物理错误']}
def sp(df):
    n = sum(x != 0 for x in df); p = sum(x > 0 for x in df)
    return sum(math.comb(n, k) for k in range(p, n+1))/2**n if n else 1.0
def summ(dd, mode, boot=False):
    ks = sorted(k for k in dd if k[1] == mode); df = [dd[k]['A']['s'] - dd[k]['B']['s'] for k in ks]
    r = {'mean_A': sum(dd[k]['A']['s'] for k in ks)/len(ks), 'mean_B': sum(dd[k]['B']['s'] for k in ks)/len(ks), 'diff': sum(df)/len(df), 'p_A': round(sp(df), 4)}
    if boot:
        rng = random.Random(0); bs = sorted(sum(rng.choice(df) for _ in df)/len(df) for _ in range(20000)); r['boot95'] = [bs[500], bs[19499]]
        se = st.stdev(df)/math.sqrt(len(df)); r['t_upper95'] = round(r['diff'] + 2.093*se, 3)
    return r
import copy
out = {}
# ① 逐题难判 4 条（solve 项）
dd = copy.deepcopy(d2); hits = []
for (i, xy) in [('SOL-02', 'Y'), ('SOL-04', 'Y'), ('SOL-01', 'Y'), ('DIA-09', 'X')]:
    for m in 'AB':
        if dd[(i, 'solve')][m]['xy'] == xy: hits.append(f'{i} {xy}={m} 原{dd[(i,"solve")][m]["s"]}'); dd[(i, 'solve')][m]['s'] = 2
out['①逐题难判4条'] = {'hits': hits, 'solve': summ(dd, 'solve'), 'acc2': {m: sum(dd[k][m]['s'] == 2 for k in dd if k[1] == 'solve')/20 for m in 'AB'}}
# ② v2 套 v1 第 1 条
dd = copy.deepcopy(d2)
for k, v in dd.items():
    for m in 'AB':
        if v[m]['phys'] == '附带':
            v[m]['s'] = 0 if k[1] in ('solve', 'socratic') else min(v[m]['s'], 1)
out['②v2附带记实质'] = {m: summ(dd, m, boot=True) for m in ('solve', 'diagnose', 'socratic')}
out['②附带条数'] = {m: sum(v[m]['phys'] == '附带' for v in d2.values()) for m in 'AB'}
# ③ v1 第 1 条按原规则
v1 = json.load(open(pathlib.Path(__file__).parent/'v1_stats.json'))
who = v1['alt1_who']; it = copy.deepcopy(v1['items'])
for tag, m in who.items():
    i = tag.split()[0]; s = it[i][m]['s2']
    it[i][m]['s2'] = 0 if it[i]['mode'] == 'solve' else min(s, 1)
dd = {(i, v['mode']): {m: {'s': v[m]['s2']} for m in 'AB'} for i, v in it.items()}
out['③v1第1条原规则'] = {m: summ(dd, m) for m in ('solve', 'diagnose')}
# ④ v2 第 7 条读法 bootstrap、⑤ 主读法 t 上界
lst7 = ['DIA-07 X','DIA-01 X','DIA-01 Y','SOL-07 X','SOL-08 X','DIA-05 Y','DIA-08 Y','DIA-02 Y','DIA-03 Y','SOL-02 X','SOL-02 Y','SOL-03 X','SOL-03 Y','SOL-05 X','SOL-09 Y','SOL-10 Y']
dd = copy.deepcopy(d2)
for k, v in dd.items():
    if k[1] == 'socratic':
        for m in 'AB':
            if f'{k[0]} {v[m]["xy"]}' in lst7 and v[m]['s'] == 1: v[m]['s'] = 2
out['④第7条读法_socratic'] = summ(dd, 'socratic', boot=True)
out['⑤主读法'] = {m: summ(d2, m, boot=True) for m in ('diagnose', 'socratic')}
json.dump(out, open(pathlib.Path(__file__).parent/'review_fix_alts.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
