"""配对 bootstrap 95% 区间（A−B 平均分差，按题重抽 20000 次，种子 0）。"""
import json, random, pathlib
o = json.load(open(pathlib.Path(__file__).parent/'v2_stats.json'))
import csv
B = pathlib.Path(__file__).resolve().parent.parent
key = json.load(open(B/'v2'/'key.json'))['pairs']; lab = {'OpenDCAI/Omni-Edu-9B': 'A', 'Qwen/Qwen3.5-9B': 'B'}
rows = list(csv.DictReader(open('./32_AI_Teaching_Lab/Teaching_Data_Spec/L26.14_v2_scores/scores.csv', encoding='utf-8-sig')))
d = {}
for r in rows:
    d.setdefault((r['题号'], r['task_mode']), {})[lab[key[f"{r['题号']}::{r['task_mode']}"][r['X/Y']]]] = int(r['0/1/2'])
rng = random.Random(0); res = {}
for mode in ('solve', 'diagnose', 'socratic'):
    df = [v['A'] - v['B'] for k, v in d.items() if k[1] == mode]
    bs = sorted(sum(rng.choice(df) for _ in df)/len(df) for _ in range(20000))
    res[mode] = {'diff': sum(df)/len(df), 'ci95': [bs[500], bs[19499]]}
print(json.dumps(res, ensure_ascii=False)); json.dump(res, open(pathlib.Path(__file__).parent/'v2_bootstrap.json', 'w'), ensure_ascii=False)
