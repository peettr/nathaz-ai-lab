#!/usr/bin/env python3
"""CRC-side read-only provenance checks and small CSV aggregation (no solver)."""
import csv
import hashlib
import json
import math
from pathlib import Path

BASE = Path('/groups/kareem/[用户]/L22_6')
TOOLS = BASE / 'L22_6_v3S0_recovery_tools_20261127'
OUT = TOOLS / 'stage0_metrics_recovered_20261127.csv'
PROVENANCE = TOOLS / 'stage0_metrics_provenance_20261127.json'
ANALYZER_SHA = '331bf927ebd9933eabb56e07c2f0911f040437cd5ffb4f2227ba2de3653bf394'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

roots = sorted(BASE.glob('L22_6_v3S0_REC_*_20261127'))
if len(roots) != 42 or OUT.exists() or PROVENANCE.exists():
    raise RuntimeError(f'expected 42 unique roots and fresh outputs: {len(roots)}')
rows, proofs = [], []
for root in roots:
    tag = root.name.removeprefix('L22_6_v3S0_REC_').removesuffix('_20261127')
    group, seq = tag.rsplit('_', 1)
    source = BASE / f'L22_6_v3S0_{tag}_20261127'
    source_probe = source / 'case/postProcessing/InletPatch/0/U'
    result = root / 'metrics.json'
    if (root / 'run.exitcode').read_text().strip() != '0':
        raise RuntimeError(f'nonzero recovery exit: {tag}')
    if sha(root / 'analyze_v3_numpy1.py') != ANALYZER_SHA:
        raise RuntimeError(f'analyzer hash mismatch: {tag}')
    if 'End' not in (source / 'pimpleFoam.log').read_text()[-2000:]:
        raise RuntimeError(f'incomplete solver: {tag}')
    if not source_probe.is_file():
        raise RuntimeError(f'missing source probe: {tag}')
    data = json.loads(result.read_text())
    if data['source_case'] != str(source / 'case') or data['source_probe'] != str(source_probe):
        raise RuntimeError(f'wrong source provenance: {tag}')
    if data['schema'] != 'L22_6_T03_stage0_raw_v3' or data['probe_spacing_m'] != 0.05 or data['record_last_s'] < 119.99:
        raise RuntimeError(f'incomplete/invalid metrics: {tag}')
    if set(data['heights']) != {'0.1','0.3','0.5','0.9','1.5'}:
        raise RuntimeError(f'wrong heights: {tag}')
    vals = {k: data[k] for k in ('max_speed_in','max_diag_in','max_rho_in','rho_xz_z15_signed_input_delta')}
    if not all(math.isfinite(v) for v in vals.values()):
        raise RuntimeError(f'nonfinite metric: {tag}')
    row = {'group': group, 'seq': seq, **vals, 'e_Ly': data['e_Ly'],
           'censored_heights': data['censored_heights'], 'source_metrics_sha256': sha(result)}
    rows.append(row)
    proofs.append({'group_seq':tag,'source_metrics':str(result),'source_metrics_sha256':row['source_metrics_sha256'],
                   'source_probe':str(source_probe),'source_probe_bytes':source_probe.stat().st_size,
                   'analyzer_sha256':ANALYZER_SHA,'record_last_s':data['record_last_s']})
if len({r['group']+'_'+r['seq'] for r in rows}) != 42:
    raise RuntimeError('duplicate tags')
with OUT.open('x',newline='') as fh:
    w = csv.DictWriter(fh,fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
with PROVENANCE.open('x') as fh:
    json.dump(proofs,fh,indent=2)
    fh.write('\n')
print(json.dumps({'rows':len(rows),'csv':str(OUT),'csv_sha256':sha(OUT),
                  'provenance':str(PROVENANCE),'provenance_sha256':sha(PROVENANCE)},ensure_ascii=False))
