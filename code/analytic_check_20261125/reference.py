#!/usr/bin/env python3
"""L26.11 analytic check (11-25, delegation #2f2eae5b): closed-form reference for the Liutex axis and Delta_R.
Independent of the code under test: the axis comes from a hand derivation (below), not from fvc::grad or any eigen-solver.

Velocity field u(x) = A x with A_ij = du_i/dx_j (Liutex convention, to be confirmed from Liu et al. 2018 card).
Cases 1-2: rigid rotation about unit axis a (rate w) plus a shear u_add = g (a.x) c, with c perp a, d = a x c:
    A = w [a]_x + g c a^T.
  In basis (a, c, d): A a = g c, A c = w d, A d = -w c  ->  eigenvalues 0, +-i w.
  Right null vector (Liutex axis r): A v = 0  ->  v = a + (g/w) d.
  Transposed tensor A^T: null vector = a  (what a code that forgets the transpose would return).
Case 3: pure strain A = Q diag(1,-0.3,-0.7) Q^T (symmetric, real eigenvalues)  ->  no Liutex axis, Delta_R = 0.
Delta_R on a hexahedral cell of sizes (hx,hy,hz): face-centre offsets +-h_k/2 e_k, so
    Delta_R = C_delta * max_k h_k * sqrt(1 - n_k^2),  C_delta = 1.035."""
import json, math
C = 1.035
def nrm(v): s = math.sqrt(sum(x*x for x in v)); return [x/s for x in v]
def add(u, v, s=1.0): return [x + s*y for x, y in zip(u, v)]
a = [1/3, 2/3, 2/3]; c = [2/3, 1/3, -2/3]; d = [-2/3, 2/3, -1/3]   # a.c = 0, d = a x c
def A_rot_shear(w, g):
    ax = [[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]]
    return [[w*ax[i][j] + g*c[i]*a[j] for j in range(3)] for i in range(3)]
def A_strain():
    lam = [1.0, -0.3, -0.7]; Q = [a, c, d]   # Q rows here = basis vectors
    return [[sum(lam[k]*Q[k][i]*Q[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
H = 0.01
MESHES = {'X': (1.0, H, H), 'Y': (H, 1.0, H), 'Z': (H, H, 1.0)}
def deltaR(n, h):
    if n is None: return 0.0
    return C * max(h[k]*math.sqrt(max(0.0, 1 - n[k]**2)) for k in range(3))
cases = {
  'C1_rot_shear_g0.5': (A_rot_shear(1.0, 0.5), nrm(add(a, d, 0.5)), a),
  'C2_rot_shear_g2':   (A_rot_shear(1.0, 2.0), nrm(add(a, d, 2.0)), a),
  'C3_pure_strain':    (A_strain(), None, None),
}
out = {}
for name, (A, r, left) in cases.items():
    ang = None if r is None else math.degrees(math.acos(min(1, abs(sum(x*y for x, y in zip(r, left))))))
    out[name] = {'A': A, 'axis_right_liutex': r, 'axis_left_transposed': left, 'angle_right_vs_left_deg': ang,
                 'deltaR_correct': {m: deltaR(r, h) for m, h in MESHES.items()},
                 'deltaR_if_transposed': {m: deltaR(left, h) for m, h in MESHES.items()}}
json.dump({'C_delta': C, 'meshes': MESHES, 'cases': out}, open(__file__.replace('reference.py', 'reference.json'), 'w'), indent=1)
for k, v in out.items():
    print(k, 'angle', v['angle_right_vs_left_deg'], 'correct', {m: round(x, 6) for m, x in v['deltaR_correct'].items()},
          'transposed', {m: round(x, 6) for m, x in v['deltaR_if_transposed'].items()})
