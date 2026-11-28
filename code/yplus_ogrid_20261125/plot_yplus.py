#!/usr/bin/env python3
"""Plot cylinder y+ (and |tau_w|) vs perimeter coordinate from a legacy ASCII VTK of the cylinder patch
(foamToVTK -patches cylinder -legacy -ascii). Face values -> face centres; spanwise mean, min, max per perimeter bin.
usage: plot_yplus.py <cylinder.vtk> <out.png> <out.json>"""
import sys, json, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
tok = open(sys.argv[1]).read().split()
def find(key, start=0): return tok.index(key, start)
i = find('POINTS'); npnt = int(tok[i + 1]); P = np.array(tok[i + 3:i + 3 + 3 * npnt], float).reshape(-1, 3)
i = find('POLYGONS'); nf = int(tok[i + 1]); k = i + 3; faces = []
for _ in range(nf):
    n = int(tok[k]); faces.append([int(t) for t in tok[k + 1:k + 1 + n]]); k += n + 1
C = np.array([P[f].mean(0) for f in faces])
def field(name):
    j = find(name, find('CELL_DATA')); ncomp = int(tok[j + 1]); n = int(tok[j + 2])
    return np.array(tok[j + 4:j + 4 + ncomp * n], float).reshape(n, ncomp)
yp = field('yPlus')[:, 0]; tw = np.linalg.norm(field('wallShearStress'), axis=1)
x, y = C[:, 0], C[:, 1]
# perimeter coordinate s from the front stagnation point (-0.5, 0), going over the top: front-top, top, rear, bottom, front-bottom
def s_of(x, y):
    e = 1e-6
    if abs(x + 0.5) < e and y >= 0: return y
    if abs(y - 0.5) < e: return 0.5 + (x + 0.5)
    if abs(x - 0.5) < e: return 1.5 + (0.5 - y)
    if abs(y + 0.5) < e: return 2.5 + (0.5 - x)
    return 3.5 + (y + 0.5)
s = np.array([s_of(a, b) for a, b in zip(x, y)])
key = np.round(s, 5); mid, inv = np.unique(key, return_inverse=True)   # one perimeter station per face column
m = np.bincount(inv, yp) / np.bincount(inv)
lo = np.full(len(mid), np.inf); hi = np.full(len(mid), -np.inf)
np.minimum.at(lo, inv, yp); np.maximum.at(hi, inv, yp)
fig, ax = plt.subplots(figsize=(9, 4.0), dpi=200)
ax.fill_between(mid, lo, hi, color='tab:blue', alpha=0.25, lw=0, label='spanwise min–max')
ax.plot(mid, m, color='tab:blue', lw=1.4, label='spanwise mean')
ymax = max(3.5, np.nanmax(hi) * 1.1); ax.set_ylim(0, ymax); ax.axhline(1, color='k', lw=0.7, ls='--')
for b, lab in zip([0, 0.5, 1.5, 2.5, 3.5, 4.0], ['front\n(stag.)', 'front-top\ncorner', 'rear-top\ncorner', 'rear-bottom\ncorner', 'front-bottom\ncorner', 'front\n(stag.)']):
    ax.axvline(b, color='0.6', lw=0.7, ls=':'); ax.text(b, ymax * 1.01, lab, ha='center', va='bottom', fontsize=7.5, clip_on=False)
ax.set_xlim(0, 4); ax.set_xlabel('perimeter coordinate s/D from the front stagnation point (over the top)')
ax.set_ylabel('$y^+$'); ax.legend(loc='center right', fontsize=8, frameon=False)
ax.set_title(pad=26, label='(g) New O-type mesh: wall $y^+$ on the cylinder, $t\\,U_\\infty/D = 6$ (inflow at full speed from $t=1$)', fontsize=9.5)
fig.tight_layout(); fig.savefig(sys.argv[2], facecolor='w')
json.dump(dict(faces=int(nf), yplus_mean=float(yp.mean()), yplus_max=float(yp.max()), yplus_min=float(yp.min()),
               area_note='face-count mean (not area-weighted)', frac_gt1=float((yp > 1).mean()), frac_gt2=float((yp > 2).mean()),
               tauw_max=float(tw.max())), open(sys.argv[3], 'w'), indent=1)
print(open(sys.argv[3]).read())
