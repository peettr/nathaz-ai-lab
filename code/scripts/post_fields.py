#!/usr/bin/env python3
"""L26.11 S1 post: zone statistics of delta fields from a reconstructed OpenFOAM case.
usage: post_fields.py <case> <t1> <t2> <out.json>   (reads <t>/{delta,hmax,hmaxOuter,IDDESDeltaDEScover.shield}, <t1>/C)"""
import sys, os, re, json, struct
import numpy as np

def read_internal(path, ncomp):
    b = open(path, 'rb').read()
    fmt_bin = b'format' in b[:2000] and re.search(rb'format\s+binary', b[:2000]) is not None
    m = re.search(rb'internalField\s+(uniform|nonuniform)', b)
    if m.group(1) == b'uniform':
        m2 = re.search(rb'internalField\s+uniform\s+([^;]+);', b)
        txt = m2.group(1).decode().strip('() ')
        return ('uniform', np.array([float(x) for x in txt.split()]))
    m3 = re.search(rb'nonuniform\s+List<\w+>\s*\n?\s*(\d+)\s*\n?\(', b[m.start():])
    n = int(m3.group(1)); start = m.start() + m3.end()
    if fmt_bin:
        arr = np.frombuffer(b[start:start + 8*n*ncomp], dtype='<f8').copy()
    else:
        end = b.index(b')\n;', start) if ncomp == 1 else b.index(b'\n)\n', start)
        txt = b[start:end].decode().replace('(', ' ').replace(')', ' ')
        arr = np.array(txt.split(), dtype=float)
    return ('nonuniform', arr.reshape(n, ncomp) if ncomp > 1 else arr)

case, t1, t2, out = sys.argv[1:5]
C = read_internal(os.path.join(case, t1, 'C'), 3)[1]
x, y = C[:, 0], C[:, 1]
zones = {
    'frontFace': (x >= -0.53) & (x <= -0.5) & (np.abs(y) <= 0.4),
    'sideWall': (x >= -0.5) & (x <= 0.5) & (np.abs(y) >= 0.5) & (np.abs(y) <= 0.53),
    'shearLayer': (x >= -0.3) & (x <= 1.5) & (np.abs(y) >= 0.55) & (np.abs(y) <= 1.0),
    'wake': (x >= 1.0) & (x <= 4.0) & (np.abs(y) <= 1.0),
    'all': np.ones_like(x, dtype=bool),
}
def fld(t, name):
    p = os.path.join(case, t, name)
    if not os.path.exists(p): return None
    kind, a = read_internal(p, 1)
    return np.full(len(x), a[0]) if kind == 'uniform' else a
res = {'case': case, 't1': t1, 't2': t2, 'nCells': int(len(x)), 'zones': {}}
F = {t: {n: fld(t, n) for n in ['delta', 'hmax', 'hmaxOuter', 'IDDESDeltaDEScover.shield']} for t in (t1, t2)}
for z, msk in zones.items():
    r = {'nCells': int(msk.sum())}
    for t in (t1, t2):
        d, h, hO, s = (F[t][k] for k in ['delta', 'hmax', 'hmaxOuter', 'IDDESDeltaDEScover.shield'])
        e = {}
        if d is not None and h is not None:
            e['mean_delta_over_hmax'] = float(np.mean(d[msk] / h[msk]))
            e['nonfinite_delta'] = int((~np.isfinite(d[msk])).sum())
        if s is not None:
            e['frac_shielded(outer=Dmax)'] = float(np.mean(s[msk] >= 0.01))
            e['mean_shield'] = float(np.mean(s[msk]))
        if hO is not None and h is not None:
            ok = np.isfinite(hO[msk])
            e['mean_hmaxOuter_over_hmax'] = float(np.mean(hO[msk][ok] / h[msk][ok])) if ok.any() else None
            e['frac_hmaxOuter_zero'] = float(np.mean(hO[msk] == 0))
            e['nonfinite_hmaxOuter'] = int((~ok).sum())
        r[t] = e
    a, b = F[t1]['hmaxOuter'], F[t2]['hmaxOuter']; h = F[t1]['hmax']
    if a is not None and b is not None:
        ok = np.isfinite(a[msk]) & np.isfinite(b[msk])
        rel = np.abs(b[msk][ok] - a[msk][ok]) / h[msk][ok]
        r['DeltaR_change'] = {'mean_abs_change_over_hmax': float(rel.mean()), 'frac_cells_changed_gt1pct_of_hmax': float(np.mean(rel > 0.01)), 'max': float(rel.max())}
    res['zones'][z] = r
json.dump(res, open(out, 'w'), indent=1)
print(json.dumps(res, indent=1))
