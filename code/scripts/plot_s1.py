#!/usr/bin/env python3
"""L26.11 S1: plot Cd/Cl and zone-averaged delta fields; write summary table. usage: plot_s1.py <dir with S1a/ S1c/ postProcessing copies> <outdir>"""
import sys, os, glob, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager
for _f in ['./Windows/Fonts/NotoSansSC-VF.ttf']:
    if os.path.exists(_f): font_manager.fontManager.addfont(_f)
plt.rcParams['font.sans-serif'] = ['Noto Sans SC', 'DejaVu Sans']; plt.rcParams['axes.unicode_minus'] = False
src, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
def load(path):
    rows = [l.split() for l in open(path) if l.strip() and not l.startswith('#')]
    return np.array(rows, dtype=float)
def hdr(path):
    h = [l for l in open(path) if l.startswith('#')][-1]; return h[1:].split('\t') if '\t' in h else h[1:].split()
runs = {'S1a 作者原样': 'S1a', 'S1c 补耦合(自 S1a t=2 续算)': 'S1c'}
col = {'S1a': '#1f77b4', 'S1c': '#d62728'}
fig, ax = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
summ = []
for lab, r in runs.items():
    f = sorted(glob.glob(f'{src}/{r}/postProcessing/forceCoeffs1/*/coefficient.dat'))[-1]
    h = [c.strip() for c in hdr(f)]; d = load(f)
    t = d[:, 0]; cd = d[:, h.index('Cd')]; cl = d[:, h.index('Cl')]
    ax[0].plot(t, cd, color=col[r], label=lab, lw=1); ax[1].plot(t, cl, color=col[r], lw=1)
    for a, b in [(2, 4), (4, 6)]:
        m = (t > a) & (t <= b)
        if m.sum() > 10: summ.append((r, f'{a}-{b}', cd[m].mean(), cl[m].std(), cl[m].mean()))
ax[0].set_ylabel('Cd'); ax[0].set_ylim(0, 3); ax[1].set_ylabel('Cl'); ax[1].set_xlabel('t U/D'); ax[0].legend(fontsize=8)
ax[0].set_title('L26.11 S1 方柱 Re=22,000 短程 Cd/Cl（本线 CRC OpenFOAM v2506 计算；未统计平稳，仅诊断）', fontsize=9)
fig.tight_layout(); fig.savefig(f'{out}/S1_CdCl.png', dpi=130)
fig, ax = plt.subplots(2, 2, figsize=(10, 6)); ax = ax.ravel()
for i, z in enumerate(['frontFace', 'sideWall', 'shearLayer', 'wake']):
    for lab, r in runs.items():
        fs = sorted(glob.glob(f'{src}/{r}/postProcessing/dstat_{z}/*/volFieldValue.dat'))
        if not fs: continue
        h = [c.strip() for c in hdr(fs[-1])]; d = load(fs[-1]); t = d[:, 0]
        hm = d[:, h.index('volAverage(hmax)')]
        ax[i].plot(t, d[:, h.index('volAverage(delta)')]/hm, color=col[r], label=f'{r} delta/hmax')
        ax[i].plot(t, d[:, h.index('volAverage(hmaxOuter)')]/hm, color=col[r], ls='--', label=f'{r} Δ_R/hmax')
        ax[i].plot(t, d[:, h.index('volAverage(IDDESDeltaDEScover.shield)')], color=col[r], ls=':', label=f'{r} 屏蔽 s')
    ax[i].set_title(z, fontsize=9); ax[i].set_xlabel('t U/D')
ax[0].legend(fontsize=6); fig.tight_layout(); fig.savefig(f'{out}/S1_zone_delta.png', dpi=130)
with open(f'{out}/S1_CdCl_summary.md', 'w') as fo:
    fo.write('| run | 时段 t | 平均 Cd | Cl 标准差 | 平均 Cl |\n|---|---|---|---|---|\n')
    for r, w, a, b, c in summ: fo.write(f'| {r} | {w} | {a:.3f} | {b:.3f} | {c:.3f} |\n')
print(open(f'{out}/S1_CdCl_summary.md').read())
