#!/usr/bin/env python3
"""L26.11 O-grid (Liang Hu 11-25 '可以试试改成O网格'). Same domain/BCs/schemes/solver as the fine H mesh
(fine_mesh_20261125); ONLY blockMeshDict topology changes: an O ring (4 blocks) square -> circle radius R,
then the 3x3 outer H frame whose middle blocks attach to the circle arcs (12 blocks total).
Wall-normal clustering stays inside the ring instead of propagating along grid lines to the far field.
usage: make_ogrid.py <outdir|-> [R] [h1] [NZ]   ('-' = design report only)"""
import sys, os, math, json, shutil, subprocess
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, '..', 'fine_mesh_20261125', 'design.py')).read().split('P = dict')[0])  # seg/section/build
out = sys.argv[1]; R = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
h1 = float(sys.argv[3]) if len(sys.argv) > 3 else 0.001; NZ = int(sys.argv[4]) if len(sys.argv) > 4 else 80
NC, face_ratio = 100, 8.0            # cells per square face / per arc (same face clustering as the fine H mesh)
a = R / math.sqrt(2); hc = (math.pi / 2) * R / NC          # circumferential spacing on the circle
XL = [-4.5, -a, a, 15.0]; YL = [-7.0, -a, a, 7.0]
# radial ring (lengths along the face-mid line, R-0.5): 0.1 band h1->0.012, then 0.012->hc
ring = [section(0.1, h1, 0.012), section(R - 0.6, 0.012, hc)]
# outer edges (straight, at x or y = +-a): wake keeps 0.035 to x~3.5, then grows to 0.35
down = [section(3.5 - a, 0.035, 0.035), section(15 - 3.5, 0.035, 0.35)]
up = [section(4.5 - a, 0.35, hc)]
side = [section(7 - a, hc, 0.35)]
def rev(s): return [(L, n, 1.0 / r) for (L, n, r) in reversed(s)]
GX = [up, [(1, NC, 1)], down]; GY = [rev(side), [(1, NC, 1)], side]
N = lambda s: sum(n for _, n, _ in s)
NR = N(ring); NX = [N(g) for g in GX]; NY = [N(g) for g in GY]
cells2d = 4 * NC * NR + sum(NX[i] * NY[j] for i in range(3) for j in range(3) if (i, j) != (1, 1))
rep = dict(R=R, h1=h1, NZ=NZ, dz=4.0 / NZ, NC=NC, NR=NR, NX=NX, NY=NY, cells=cells2d * NZ, cells_per_layer=cells2d,
           hc=hc, ring=ring, GX=GX, GY=GY,
           corner_tangential=build([(0.5, NC // 2, face_ratio)])[0],
           first_cell_mid=h1, first_cell_diag=h1 * (R - math.sqrt(0.5)) / (R - 0.5),
           ring_last_mid=build(ring)[-1] * 1.0, max_adj={k: max(max(d[i+1]/d[i], d[i]/d[i+1]) for i in range(len(d)-1))
           for k, d in dict(ring=build(ring), down=build(down), up=build(up), side=build(side)).items()})
if out == '-':
    print(json.dumps({k: v for k, v in rep.items() if k not in ('ring', 'GX', 'GY')}, indent=None)); sys.exit()
# ---- base case = fine H case (same BCs/schemes/solver/function objects), then replace blockMeshDict and 0/ ----
fine = os.path.join(here, '..', 'fine_mesh_20261125')
subprocess.check_call([sys.executable, os.path.join(fine, 'make_case_fine.py'), out, os.path.join(fine, 'design_h0.001_nz80.json'),
                       '6.0', '0.0002', '6.0', '0.0002'], stdout=subprocess.DEVNULL)
for f in os.listdir(os.path.join(fine, 'case_check3', '0')):      # ramped-inlet start fields (check 3, worked)
    shutil.copy(os.path.join(fine, 'case_check3', '0', f), os.path.join(out, '0', f))
ms = lambda secs: '(' + ' '.join('(%.6g %d %.6g)' % s for s in secs) + ')'
s2 = 1 / math.sqrt(2)
pts = [(-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5)]          # 0-3 square corners SA SB SC SD
pid = {}
for j in range(4):
    for i in range(4):
        pid[(i, j)] = len(pts); pts.append((XL[i], YL[j]))   # outer frame; (1,1),(2,1),(2,2),(1,2) are circle points
C = [pid[(1, 1)], pid[(2, 1)], pid[(2, 2)], pid[(1, 2)]]     # CA CB CC CD
NP = len(pts); v = lambda p, k: p + NP * k
verts = [(x, y, z) for z in (0.0, 4.0) for (x, y) in pts]
def hexs(q): return ' '.join(str(v(p, 0)) for p in q) + ' ' + ' '.join(str(v(p, 1)) for p in q)
blocks, faces = [], {k: [] for k in ('inlet', 'outlet', 'bottom', 'top', 'cylinder', 'front', 'back')}
LF = {"xmin": (0, 4, 7, 3), "xmax": (1, 2, 6, 5), "ymin": (0, 1, 5, 4), "ymax": (3, 7, 6, 2), "zmin": (0, 3, 2, 1), "zmax": (4, 5, 6, 7)}
def addface(q, f, patch):
    hx = [v(p, 0) for p in q] + [v(p, 1) for p in q]; faces[patch].append('(' + ' '.join(str(hx[k]) for k in LF[f]) + ')')
clus = '((0.5 %d %g) (0.5 %d %g))' % (NC // 2, face_ratio, NC // 2, 1 / face_ratio)
for f in range(4):   # ring: x1 radial (square corner -> circle point), x2 CCW along the face
    q = [f, C[f], C[(f + 1) % 4], (f + 1) % 4]
    eg = ' '.join([ms(ring)] * 4 + [clus, '1', '1', clus] + ['1'] * 4)
    blocks.append('    hex (%s) (%d %d %d) edgeGrading (%s)' % (hexs(q), NR, NC, NZ, eg))
    addface(q, 'xmin', 'cylinder'); addface(q, 'zmin', 'front'); addface(q, 'zmax', 'back')
for j in range(3):
    for i in range(3):
        if (i, j) == (1, 1): continue
        q = [pid[(i, j)], pid[(i + 1, j)], pid[(i + 1, j + 1)], pid[(i, j + 1)]]
        blocks.append('    hex (%s) (%d %d %d) simpleGrading (%s %s 1)' % (hexs(q), NX[i], NY[j], NZ, ms(GX[i]), ms(GY[j])))
        if i == 0: addface(q, 'xmin', 'inlet')
        if i == 2: addface(q, 'xmax', 'outlet')
        if j == 0: addface(q, 'ymin', 'bottom')
        if j == 2: addface(q, 'ymax', 'top')
        addface(q, 'zmin', 'front'); addface(q, 'zmax', 'back')
mid = [(0, -R), (R, 0), (0, R), (-R, 0)]
edges = ['    arc %d %d (%.9g %.9g %g)' % (v(C[f], k), v(C[(f + 1) % 4], k), mid[f][0], mid[f][1], z)
         for f in range(4) for k, z in ((0, 0.0), (1, 4.0))]
types = dict(inlet='patch', outlet='patch', bottom='patch', top='patch', cylinder='wall')
bnd = ['    %s { type %s; faces (%s); }' % (n, types[n], ' '.join(faces[n])) for n in types]
bnd += ['    front { type cyclic; neighbourPatch back; faces (%s); }' % ' '.join(faces['front']),
        '    back { type cyclic; neighbourPatch front; faces (%s); }' % ' '.join(faces['back'])]
bm = os.path.join(out, 'system/blockMeshDict'); hdr = open(bm).read().split('scale')[0]
open(bm, 'w').write(hdr + 'scale 1;\nvertices\n(\n' + '\n'.join('    (%.9g %.9g %g)' % p for p in verts) + '\n);\nblocks\n(\n' +
                    '\n'.join(blocks) + '\n);\nedges\n(\n' + '\n'.join(edges) + '\n);\nboundary\n(\n' + '\n'.join(bnd) + '\n);\nmergePatchPairs ();\n')
# check-run controlDict: ramped inlet from rest, adaptive dt from the start (maxCo 0.9), one write at endTime
cd = os.path.join(out, 'system/controlDict'); c = open(cd).read()
c = c.replace('writeControl    runTime;', 'writeControl    adjustableRunTime;\nadjustTimeStep  yes;\nmaxCo           0.9;\nmaxDeltaT       0.002;')
open(cd, 'w').write(c)
os.remove(os.path.join(out, 'stages.json'))
json.dump(rep, open(os.path.join(out, 'ogrid_design.json'), 'w'), indent=1)
print('written', out, 'cells expected', rep['cells'])
