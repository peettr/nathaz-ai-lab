#!/usr/bin/env python3
"""Map cell labels of a checkMesh cellSet to block/position using blockMesh ordering (blocks in dict order,
i fastest, then j, then k) and the design spacing arrays. usage: locate_set.py <design.json> <cellSet file>"""
import json, sys, re, collections
exec(open(__file__.replace('locate_set.py', 'design.py')).read().split('P = dict')[0])
d = json.load(open(sys.argv[1]))
dx = [build([tuple(s) for s in g]) for g in d['GX']]; dy = [build([tuple(s) for s in g]) for g in d['GY']]
NX, NY, NZ = d['NX'], d['NY'], d['NZ']
X0 = [-4.5, -0.5, 0.5]; Y0 = [-7, -0.5, 0.5]
order = [(i, j) for j in range(3) for i in range(3) if (i, j) != (1, 1)]
starts = []; s = 0
for (i, j) in order: starts.append(s); s += NX[i] * NY[j] * NZ
txt = open(sys.argv[2]).read(); body = txt[txt.index('(', txt.index('}')) + 1: txt.rindex(')')]
labels = [int(x) for x in body.split()]
xc = [[X0[i] + sum(dx[i][:k]) + dx[i][k] / 2 for k in range(NX[i])] for i in range(3)]
yc = [[Y0[j] + sum(dy[j][:k]) + dy[j][k] / 2 for k in range(NY[j])] for j in range(3)]
cnt = collections.Counter(); focus = 0; ex = []
for L in labels:
    b = max(k for k in range(8) if starts[k] <= L); i, j = order[b]; r = L - starts[b]
    ii = r % NX[i]; jj = (r // NX[i]) % NY[j]
    x, y = xc[i][ii], yc[j][jj]
    cnt[(i, j)] += 1
    if -1 < x < 4 and -1.5 < y < 1.5: focus += 1
    if len(ex) < 6 and len(labels) and L % 50000 == 0: ex.append((round(x, 3), round(y, 3), round(dx[i][ii], 4), round(dy[j][jj], 4)))
print('cells in set', len(labels), 'by block', dict(cnt), 'in focus box x(-1,4) y(-1.5,1.5):', focus)

