"""Seeded-random interior wind variant of run.py; separate outputs (no overwrites)."""
import random, json, time
from pathlib import Path
import run as m
m.RANDOM_WIND=random.Random(0).choice([10,20,30])
assert m.RANDOM_WIND==20
m.OUT=Path('/content/tpu_out_seed0');m.OUT.mkdir(exist_ok=True)
t=time.time();cases=[]
for b in m.BUILDINGS:
    for a in m.ANGLES:
        cases.append(m.load_case(b,a));print('loaded',b,a,flush=True)
m.by={(c['b'],c['angle']):c for c in cases}
rows=m.evaluate(cases,'building')+m.evaluate(cases,'wind')
(m.OUT/'metrics_seed0.json').write_text(json.dumps({'seed':0,'random_wind':m.RANDOM_WIND,'rows':rows,
    'manifest':[{'building':c['b'],'angle':c['angle'],'taps':len(c['y']),
    'n_time':c['n_time'],'sample_frequency_hz':c['frequency'],
    'bytes':c['size_bytes'],'url':c['url']} for c in cases],
    'elapsed_seconds':time.time()-t},indent=2))
print('seed',0,'random wind',m.RANDOM_WIND,'rows',json.dumps(rows),flush=True)
