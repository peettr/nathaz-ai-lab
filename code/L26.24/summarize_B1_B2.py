import csv
import json
import statistics
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

root = Path(__file__).resolve().parent
archive = root / 'B1_B2_rows_20261115.tar.gz'
rows = []
counts = Counter()
with tarfile.open(archive) as tar:
    members = [m for m in tar.getmembers() if '/rows/' in m.name and m.name.endswith('.json')]
    for m in members:
        item = json.load(tar.extractfile(m))
        baseline = m.name.split('/')[0]
        segment, target = item['segment'], item['target']
        counts[(baseline, segment, target)] += 1
        assert len(item['results']) == 5, m.name
        for r in item['results']:
            assert r['status'] == 'converged' and r['achieved_residual'] <= item['target_residual'] * (1 + 1e-9), (m.name, r)
            rows.append(dict(baseline=baseline, segment=segment, system=item['system'], target=target,
                             repetition=r['repetition'], n=item['n'], nnz=item['nnz'],
                             initial_residual=item['initial_residual'], target_residual=item['target_residual'],
                             setup_seconds=r['setup_seconds'], solve_seconds=r['solve_seconds'],
                             total_seconds=r['total_seconds'], iterations=r['iterations'],
                             achieved_residual=r['achieved_residual'], status=r['status'], cpu_model=item['cpu_model']))
assert len(members) == 240 and len(rows) == 1200
assert all(counts[(b,s,t)] == 20 for b in ('B1','B2') for s in ('t0','restart','later') for t in ('Ta','Tb'))
rows.sort(key=lambda r: (r['baseline'], r['segment'], r['system'], r['target'], r['repetition']))
with (root/'baseline_timing_B1_B2_partial.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
by_system = defaultdict(list)
for r in rows:
    if r['segment'] == 'later':
        by_system[(r['baseline'], r['target'], r['system'])].append(r['total_seconds'])
summary = {'status':'partial_B1_B2_only_B0_not_submitted', 'systems_per_baseline':60,
           'rows_per_baseline':600, 'source_archive':str(archive), 'cpu':'AMD EPYC 7451 24-Core Processor',
           'threads':{'OMP_NUM_THREADS':1,'OPENBLAS_NUM_THREADS':1,'MKL_NUM_THREADS':1}, 'test':{}}
for b in ('B1','B2'):
    summary['test'][b] = {}
    for t in ('Ta','Tb'):
        vals = [statistics.median(v) for (bb,tt,_),v in by_system.items() if (bb,tt)==(b,t)]
        assert len(vals)==20
        vals.sort()
        q1, med, q3 = statistics.quantiles(vals,n=4,method='inclusive')[0], statistics.median(vals), statistics.quantiles(vals,n=4,method='inclusive')[2]
        summary['test'][b][t] = {'systems':20,'repetitions':5,'median_total_seconds':med,'q1_seconds':q1,'q3_seconds':q3,'iqr_seconds':q3-q1,'quantile_method':'inclusive linear interpolation of 20 per-system 5-run medians'}
(root/'baseline_summary_B1_B2_partial.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
