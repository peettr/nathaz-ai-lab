#!/usr/bin/env python3
"""Assert frozen T15 empty-field gate classification against archived metrics."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent
v = json.loads((R/'T15_verdict.json').read_text())
assert set(v['seeds']) == {'107','108','109'}
rows = {}
for seed, s in v['seeds'].items():
    assert s['wall_tau_columns'] > 0 and s['wall_tau_nonzero_fraction'] > 0
    assert s['profile_rows'] == 51
    assert s['strip_tau_rows'] == 0 and s['strip_ustar_mps'] is None
    assert abs(s['H']-s['G_xc_2m_mps']/s['G_x5_2m_mps']) < 1e-12
    assert abs(s['delta_H_vs_bounce']-(s['H']-s['H_bounce_1m'])) < 1e-12
    assert abs(s['ustar_ratio']-s['ustar_fetch_mid_mps']/s['ustar_design_inlet_mps']) < 1e-12
    rows[seed] = {'G1':s['H']>=.8 and s['delta_H_vs_bounce']>=.1,
                  'G2':s['profile_max_deviation']<=.05,
                  'G3':.9<=s['ustar_ratio']<=1.1}
for gate in ('G1','G2','G3'):
    assert v[gate]['pass'] == all(row[gate] for row in rows.values())
if all(v[g]['pass'] for g in ('G1','G2','G3')): expected='通过（仅空场）'
elif v['G1']['pass']: expected='中间'
elif all(s['delta_H_vs_bounce']<=.03 for s in v['seeds'].values()): expected='无改善'
else: expected='中间'
assert v['verdict']==expected
print(json.dumps({'seed_gates':rows,'aggregate':{g:v[g]['pass'] for g in ('G1','G2','G3')},'verdict':expected},ensure_ascii=False,indent=2))
