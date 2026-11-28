#!/usr/bin/env python3
"""L22.11 v2 y+ 门（实验卡 EXPERIMENT_CARD_v2.md ③）：读基线 yPlus 的建筑五面 vtp，按面积统计墙面（四面合并）与屋面的
加权中位、95 分位、<30 / 30–300 / >300 面积占比。两组中位都在 [30,300] → 退出 0，否则退出 3。用法：ypgate.py <VTK目录> <输出json>"""
import sys, re, glob, json, numpy as np
d, out = sys.argv[1:3]
def arr(x, name):
    m = re.search(r"<DataArray[^>]*Name=[\"']%s[\"'][^>]*>(.*?)</DataArray>" % re.escape(name), x, re.S); return np.array(m.group(1).split(), float)
def read_vtp(p):
    x = open(p).read(); A = []; V = []
    for pc in x.split('<Piece')[1:]:
        pts = np.array(re.search(r"<Points>\s*<DataArray[^>]*>(.*?)</DataArray>", pc, re.S).group(1).split(), float).reshape(-1, 3)
        con = arr(pc, 'connectivity').astype(int); off = arr(pc, 'offsets').astype(int); f = arr(pc, 'yPlus'); st = np.r_[0, off[:-1]]
        for a, b, v in zip(st, off, f):
            q = pts[con[a:b]]; A.append(sum(.5 * np.linalg.norm(np.cross(q[j] - q[0], q[j + 1] - q[0])) for j in range(1, len(q) - 1))); V.append(v)
    return np.array(A), np.array(V)
def wq(v, a, q):
    o = np.argsort(v); c = np.cumsum(a[o]) / a.sum(); return float(v[o][np.searchsorted(c, q)])
res = {}
for grp, pats in (('walls', ['xneg', 'xpos', 'yneg', 'ypos']), ('roof', ['roof'])):
    A = []; V = []
    for pa in pats:
        fs = sorted(glob.glob(f'{d}/**/{pa}.vtp', recursive=True)); assert len(fs) == 1, (pa, fs)
        a, v = read_vtp(fs[0]); A.append(a); V.append(v)
    A = np.concatenate(A); V = np.concatenate(V)
    res[grp] = {'faces': int(len(V)), 'area': float(A.sum()), 'median': wq(V, A, .5), 'p05': wq(V, A, .05), 'p95': wq(V, A, .95),
                'share_lt30': float(A[V < 30].sum() / A.sum()), 'share_30_300': float(A[(V >= 30) & (V <= 300)].sum() / A.sum()),
                'share_gt300': float(A[V > 300].sum() / A.sum())}
res['pass'] = all(30 <= res[g]['median'] <= 300 for g in ('walls', 'roof'))
json.dump(res, open(out, 'w'), indent=2); print(json.dumps(res))
sys.exit(0 if res['pass'] else 3)
