#!/usr/bin/env python3
"""Cell sizes of the L26.11 square-cylinder blockMesh (medium and coarse) computed from the generator's
grading definitions (base_make_case.py sha 30fa3281 / base_make_case_coarse.py sha 0425e350), using
OpenFOAM simpleGrading semantics (expansion ratio = last cell / first cell; multi-grading sections
(length fraction, cell fraction, ratio))."""
import json, math
def seg(L, n, r):
    if n == 1: return [L]
    q = r ** (1.0 / (n - 1))
    if abs(q - 1) < 1e-14: return [L / n] * n
    a = L * (1 - q) / (1 - q ** n); return [a * q ** k for k in range(n)]
def edge(L, N, g):
    if isinstance(g, (int, float)): return seg(L, N, g)
    tot_c = sum(s[1] for s in g); tot_l = sum(s[0] for s in g)
    ns = [round(N * s[1] / tot_c) for s in g]; ns[-1] = N - sum(ns[:-1])
    out = []
    for (lf, cf, r), n in zip(g, ns): out += seg(L * lf / tot_l, n, r)
    return out
GX = [0.0184, [(0.5, 0.5, 8), (0.5, 0.5, 0.125)], [(0.1, 40, 26), (0.9, 110, 1)]]
GY = [0.0098, [(0.5, 0.5, 8), (0.5, 0.5, 0.125)], 102]
X = [-4.5, -0.5, 0.5, 15.0]; Y = [-7.0, -0.5, 0.5, 7.0]
MESH = {'medium': ([64, 64, 150], [64, 64, 64], 40), 'coarse': ([43, 43, 100], [43, 43, 43], 27)}
res = {}
for m, (NX, NY, NZ) in MESH.items():
    dx = [edge(X[i+1]-X[i], NX[i], GX[i]) for i in range(3)]
    dy = [edge(Y[j+1]-Y[j], NY[j], GY[j]) for j in range(3)]
    dz = 4.0 / NZ
    cells = sum(NX[i]*NY[j] for i in range(3) for j in range(3) if (i, j) != (1, 1)) * NZ
    front_first = dx[0][-1]; rear_first = dx[2][0]; side_first = dy[2][0]          # wall-normal first cells
    along = dx[1]                                                                     # along side face (corner clustered)
    # shear-layer start region: above the side face, x in [-0.5,0.5], y in [0.5, 0.7]
    ys = [0.5]; [ys.append(ys[-1] + h) for h in dy[2]]
    ny_sl = sum(1 for k in range(len(dy[2])) if ys[k] < 0.7)
    dy_sl = dy[2][:ny_sl]
    # wake: rear block, graded part (x 0.5-1.95) then uniform
    wake_unif = dx[2][-1]; xs = [0.5]; [xs.append(xs[-1] + h) for h in dx[2]]
    dx_at = lambda x: dx[2][max(k for k in range(len(dx[2])) if xs[k] <= x)]
    r = {'cells': cells, 'NZ': NZ, 'dz': dz,
         'first_cell_wall_normal': {'front_face_dx': front_first, 'side_faces_dy': side_first, 'rear_face_dx': rear_first},
         'along_face_spacing': {'min_at_corner': min(along), 'max_mid_face': max(along)},
         'shear_layer_start_y0.5to0.7': {'n_cells_in_y': ny_sl, 'dy_min': min(dy_sl), 'dy_max': max(dy_sl),
             'dx_range_over_side': [min(along), max(along)], 'dz': dz,
             'aspect_dz_over_dx_at_corner': dz / min(along), 'aspect_dz_over_dx_mid': dz / max(along),
             'aspect_dz_over_dy_at_y0.6': dz / dy[2][max(k for k in range(len(dy[2])) if ys[k] <= 0.6)],
             'aspect_dx_mid_over_dy_at_y0.6': max(along) / dy[2][max(k for k in range(len(dy[2])) if ys[k] <= 0.6)]},
         'wake': {'dx_at_x=1': dx_at(1.0), 'dx_at_x=2': dx_at(2.0), 'dx_uniform_x>1.95': wake_unif,
                  'dy_on_centreline_band_|y|<0.5': [min(dy[1]), max(dy[1])]},
         'domain': {'x': [X[0], X[-1]], 'y': [Y[0], Y[-1]], 'z': [0, 4.0], 'upstream_from_front_face_D': 4.0,
                    'downstream_from_rear_face_D': 14.5, 'blockage': 1 / 14}}
    res[m] = r
json.dump(res, open(__file__.replace('mesh_stats.py', 'mesh_stats.json'), 'w'), indent=1)
for m, r in res.items():
    print(m, json.dumps(r, indent=None)[:2000]); print()
