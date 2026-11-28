#!/usr/bin/env python3
"""L22.11 clean 门 A（卡 ③，11-25 21:10 写定）：三档网格质量门。用法：gateA.py <mesh根目录（含 coarse/ medium/ fine/）> <输出json>
每档目录需有 checkMesh.log、snappyHexMesh.log、boundary、VTK/（time 0 的建筑五面 vtp）。全部满足退出 0，否则 4。"""
import sys, re, glob, json, numpy as np
root, out = sys.argv[1:3]
WANT = {'inlet', 'outlet', 'sideNeg', 'sidePos', 'ground', 'top', 'xneg', 'xpos', 'yneg', 'ypos', 'roof'}
AREA = {'xneg': 128., 'xpos': 128., 'yneg': 128., 'ypos': 128., 'roof': 256.}
def arr(x, name):
    m = re.search(r"<DataArray[^>]*Name=[\"']%s[\"'][^>]*>(.*?)</DataArray>" % re.escape(name), x, re.S); return np.array(m.group(1).split(), float)
def area(p):
    x = open(p).read(); A = 0.
    for pc in x.split('<Piece')[1:]:
        pts = np.array(re.search(r"<Points>\s*<DataArray[^>]*>(.*?)</DataArray>", pc, re.S).group(1).split(), float).reshape(-1, 3)
        con = arr(pc, 'connectivity').astype(int); off = arr(pc, 'offsets').astype(int); st = np.r_[0, off[:-1]]
        for a, b in zip(st, off):
            q = pts[con[a:b]]; A += sum(.5 * np.linalg.norm(np.cross(q[j] - q[0], q[j + 1] - q[0])) for j in range(1, len(q) - 1))
    return A
res = {}; ok = True
for g in ('coarse', 'medium', 'fine'):
    d = f'{root}/{g}'; cm = open(f'{d}/checkMesh.log').read(); sn = open(f'{d}/snappyHexMesh.log').read(); bd = open(f'{d}/boundary').read()
    names = set(re.findall(r'^\s*([A-Za-z]\w*)\s*\n\s*\{', bd, re.M)) - {'FoamFile'}
    bb = [float(v) for v in re.search(r'Overall domain bounding box \(([^)]*)\) \(([^)]*)\)', cm).groups()[0].split() + re.search(r'Overall domain bounding box \(([^)]*)\) \(([^)]*)\)', cm).groups()[1].split()]
    N = int(re.search(r'^\s*cells:\s+(\d+)', cm, re.M).group(1)); V = float(re.search(r'Total volume = ([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)', cm).group(1))
    sk = float(re.search(r'Max skewness = ([0-9.eE+-]+)', cm).group(1)); no = float(re.search(r'non-orthogonality Max: ([0-9.eE+-]+)', cm).group(1))
    tabs = re.findall(r'patch\s+faces\s+layers\s+overall thickness.*?\n((?:.*\n){3,12}?)\s*\n', sn)
    lay = {}
    for line in (tabs[-1] if tabs else '').splitlines():
        f = line.split()
        if f and f[0] in AREA: lay[f[0]] = {'faces': int(f[1]), 'target': float(f[2]), 'mesh': float(f[3]), 'thick_m': float(f[4]), 'pct': float(f[5])}
    ar = {}
    for pa in AREA:
        fs = sorted(glob.glob(f'{d}/VTK/**/{pa}.vtp', recursive=True)); ar[pa] = sum(area(f) for f in fs) if fs else float('nan')
    c = {
        '1_meshOK': 'Mesh OK' in cm,
        '2_patches11': names == WANT,
        '3_areas': all(abs(ar[p] - AREA[p]) / AREA[p] <= 1e-4 for p in AREA),
        '4_bbox': abs(bb[2]) <= 1e-9 and np.allclose(bb, [-48, -48, 0, 136, 48, 64], atol=1e-6),
        '5_layers': len(lay) == 5 and all(v['mesh'] >= 4.95 and v['pct'] >= 99 for v in lay.values()),
        '6_quality': sk <= 2.5 and no <= 60}
    res[g] = {'cells': N, 'volume': V, 'h': (V / N) ** (1 / 3), 'patches': sorted(names), 'bbox': bb, 'areas': ar, 'layers': lay, 'max_skewness': sk, 'max_nonortho': no, 'checks': c}
    ok &= all(c.values())
r21 = res['medium']['h'] / res['fine']['h']; r32 = res['coarse']['h'] / res['medium']['h']
res['r21'] = r21; res['r32'] = r32; res['7_ratio'] = 1.25 <= r21 <= 1.5 and 1.25 <= r32 <= 1.5
ok &= res['7_ratio']; res['pass'] = bool(ok)
json.dump(res, open(out, 'w'), indent=1); print(json.dumps({g: (res[g]['cells'], res[g]['checks']) for g in ('coarse', 'medium', 'fine')}), r21, r32, 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 4)
