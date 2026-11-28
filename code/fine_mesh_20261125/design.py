#!/usr/bin/env python3
"""L26.11 fine-mesh design (Liang Hu 11-25 '做一个好一点的网格试试，先检查网格再算').
Same topology/domain/BCs as the L26.11 meshes; only spacing changes. Builds OpenFOAM multi-grading
sections from wall-outward targets, then re-evaluates every edge with simpleGrading semantics."""
import json, math, sys
def seg(L, n, r):
    if n == 1: return [L]
    q = r ** (1.0 / (n - 1))
    if abs(q - 1) < 1e-14: return [L / n] * n
    a = L * (1 - q) / (1 - q ** n); return [a * q ** k for k in range(n)]
def section(L, h0, h1):
    """n cells over length L going from ~h0 to ~h1 (geometric); returns (L, n, ratio last/first)."""
    if abs(h1 - h0) < 1e-12: n = max(1, round(L / h0)); return (L, n, 1.0)
    q_guess = (L - h0) / (L - h1) if L > h1 else 1.1
    n = max(2, round(math.log(h1 / h0) / math.log(q_guess)) + 1)
    return (L, n, h1 / h0)
def build(sections):   # sections from START to END of the block edge, each (L, n, ratio)
    out = []
    for L, n, r in sections: out += seg(L, n, r)
    return out
P = dict(h1=float(sys.argv[1]) if len(sys.argv) > 1 else 0.001, NZ=int(sys.argv[2]) if len(sys.argv) > 2 else 80,
         n_face=100, face_ratio=8.0, band=0.1, focus_end=0.6, h_focus=0.025, h_far=0.35, wake_focus_end=3.5, h_wake=0.035)
h1 = P['h1']
# wall-outward pieces
near = section(P['band'], h1, 0.012)
focus = section(P['focus_end'] - P['band'], 0.012, P['h_focus'])
def outward(far_len):
    far = section(far_len, P['h_focus'], P['h_far']); return [near, focus, far]
up = outward(4.0 - P['focus_end'])          # upstream block x: -4.5 -> -0.5 (wall at END) -> reverse
side = outward(6.5 - P['focus_end'])        # top block y: 0.5 -> 7 (wall at START)
wake = [near, section(P['wake_focus_end'] - P['band'] - 0.5 + 0.5 - 0, 0.012, P['h_wake']),
        section(15.0 - 0.5 - P['wake_focus_end'], P['h_wake'], P['h_far'])]
def rev(secs): return [(L, n, 1.0 / r) for (L, n, r) in reversed(secs)]
half = (0.5, P['n_face'] // 2, P['face_ratio']); face = [half, (0.5, P['n_face'] // 2, 1.0 / P['face_ratio'])]
GX = [rev(up), face, wake]; GY = [rev(side), face, side]
dx = [build(g) for g in GX]; dy = [build(g) for g in GY]
NX = [len(d) for d in dx]; NY = [len(d) for d in dy]; NZ = P['NZ']; dz = 4.0 / NZ
cells = sum(NX[i] * NY[j] for i in range(3) for j in range(3) if (i, j) != (1, 1)) * NZ
def maxjump(d): return max(max(d[k+1] / d[k], d[k] / d[k+1]) for k in range(len(d) - 1))
ys = [0.5]; [ys.append(ys[-1] + h) for h in dy[2]]
def at(dl, origin, x): pos = origin; 
rep = {'params': P, 'NX': NX, 'NY': NY, 'NZ': NZ, 'cells': cells, 'dz': dz,
       'first_cell': {'front': dx[0][-1], 'side': dy[2][0], 'rear': dx[2][0]},
       'face_spacing_corner_mid': [min(dx[1]), max(dx[1])],
       'max_adjacent_ratio': {'upstream': maxjump(dx[0]), 'face': maxjump(dx[1]), 'wake': maxjump(dx[2]), 'side': maxjump(dy[2])},
       'cells_within_0.1D': sum(1 for k in range(len(dy[2])) if ys[k + 1] <= 0.1 + 0.5 + 1e-12),
       'shear_layer_y0.5_0.7': {'n': sum(1 for k in range(len(dy[2])) if ys[k] < 0.7), 'dy_range': [dy[2][0], dy[2][sum(1 for k in range(len(dy[2])) if ys[k] < 0.7) - 1]]},
       'aspect_dz_over_dx': {'corner': dz / min(dx[1]), 'mid_face': dz / max(dx[1])},
       'wake_dx_x1_x3': [dx[2][sum(1 for h in [0] for _ in [0])]],
       'GX': GX, 'GY': GY}
xs = [0.5]; [xs.append(xs[-1] + h) for h in dx[2]]
rep['wake_dx'] = {x: dx[2][max(k for k in range(len(dx[2])) if xs[k] <= x)] for x in (0.6, 1.0, 2.0, 3.0, 5.0, 10.0)}
del rep['wake_dx_x1_x3']
json.dump(rep, open(__file__.replace('design.py', f'design_h{h1}_nz{NZ}.json'), 'w'), indent=1)
print(json.dumps({k: v for k, v in rep.items() if k not in ('GX', 'GY', 'params')}, indent=None))
