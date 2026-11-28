#!/usr/bin/env python3
"""Compare library Delta (results_raw.txt) with the closed-form reference (reference.json) using the pre-written criteria."""
import json, math, re, os
here = os.path.dirname(os.path.abspath(__file__))
ref = json.load(open(f'{here}/reference.json')); C = ref['C_delta']
res = {}
for l in open(f'{here}/results_raw.txt'):
    m = re.match(r'OUT (\S+) (\S+) (\S+) RESULT cell \d+ C \(.*?\) delta (\S+) gradU_OF \((.*)\)', l)
    if m: res[(m[1], m[2], m[3])] = (float(m[4]), [float(x) for x in m[5].split()])
rows, verdict = [], {}
for lib in ('paper', 'v3'):
    ok = True; match_transposed = True
    for case, v in ref['cases'].items():
        A = v['A']; AT = [A[j][i] for i in range(3) for j in range(3)]
        gerr = max(max(abs(a - b) for a, b in zip(res[(lib, m, case)][1], AT)) for m in ref['meshes'])
        if v['axis_right_liutex'] is None:
            dl = {m: res[(lib, m, case)][0] for m in ref['meshes']}
            p = all(abs(x) <= 1e-12 for x in dl.values()); ok &= p
            rows.append((lib, case, dl, None, None, None, None, gerr, p)); continue
        dl = {m: res[(lib, m, case)][0] for m in ref['meshes']}
        rc = v['deltaR_correct']; rt = v['deltaR_if_transposed']
        rel = max(abs(dl[m] - rc[m]) / rc[m] for m in dl)
        relT = max(abs(dl[m] - rt[m]) / rt[m] for m in dl)
        # reconstruct |n_k| from the mesh whose long side is along k (neglect the 0.01 terms)
        nk = [math.sqrt(max(0.0, 1 - (dl[m] / C) ** 2)) for m in ('X', 'Y', 'Z')]
        nn = math.sqrt(sum(x * x for x in nk)); nk = [x / nn for x in nk]
        r = [abs(x) for x in v['axis_right_liutex']]
        ang = math.degrees(math.acos(min(1.0, sum(a * b for a, b in zip(nk, r)))))
        p = rel <= 1e-4 and ang <= 0.5; ok &= p; match_transposed &= relT <= 1e-4
        rows.append((lib, case, dl, rc, rel, ang, relT, gerr, p))
    verdict[lib] = {'pass': bool(ok), 'matches_transposed_reference': bool(match_transposed)}
valid = (not verdict['v3']['pass']) and verdict['v3']['matches_transposed_reference']
out = {'rows': [dict(lib=r[0], case=r[1], delta_lib=r[2], delta_ref_correct=r[3], max_rel_err_vs_correct=r[4],
                     axis_angle_deg_abs_components=r[5], max_rel_err_vs_transposed=r[6], gradU_vs_AT_max_abs=r[7], pass_=r[8]) for r in rows],
       'verdict': verdict, 'test_valid': valid}
json.dump(out, open(f'{here}/comparison.json', 'w'), indent=1)
for r in rows:
    print(r[0], r[1], {k: round(x, 6) for k, x in r[2].items()}, 'ref', None if r[3] is None else {k: round(x, 6) for k, x in r[3].items()},
          'rel', None if r[4] is None else f'{r[4]:.1e}', 'ang', None if r[5] is None else f'{r[5]:.3f}', 'relT', None if r[6] is None else f'{r[6]:.1e}', 'gradErr', f'{r[7]:.1e}', 'PASS' if r[8] else 'FAIL')
print(verdict, 'test_valid', valid)
