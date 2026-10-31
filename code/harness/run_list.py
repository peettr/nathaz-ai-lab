"""Run L26.10 cases sequentially (one Fluent licence at a time).

Usage: python run_list.py <list.json> <runroot>
list.json: [{"id": "A_clean_1", "harness": "a"|"b", "inj": {...} | "args": [...]}, ...]
Each run: <runroot>/runs/<id>/run.log, out/ (Fluent root), time.json.
"""
import json, os, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
lst = json.loads(Path(sys.argv[1]).read_text())
rr = Path(sys.argv[2]).resolve()
py = sys.executable
for item in lst:
    d = rr / 'runs' / item['id']
    if (d / 'time.json').exists():
        print('SKIP_DONE', item['id'], flush=True); continue
    d.mkdir(parents=True, exist_ok=True)
    if item['harness'] == 'a':
        cmd = [py, str(HERE / 'l2610_a.py'), '--snapshot', str(rr / 'snapshot'), '--root', str(d / 'out'),
               '--inj', json.dumps(item.get('inj', {}))]
    else:
        cmd = [py, str(HERE / 'l2610_b.py'), '--source', str(rr / 'baseB' / 'segment_final.cas.h5'),
               '--root', str(d / 'out')] + item.get('args', [])
    t0 = time.time()
    with open(d / 'run.log', 'w') as log:
        rc = subprocess.call(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=str(d))
    (d / 'time.json').write_text(json.dumps({'id': item['id'], 'rc': rc, 'seconds': time.time() - t0, 'end': time.strftime('%m-%d %H:%M')}))
    print('RUN', item['id'], 'rc', rc, 'sec', round(time.time() - t0), flush=True)
print('ALL_DONE', flush=True)
