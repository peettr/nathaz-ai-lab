"""L22.10 M2 准备：TPU 子集屋面测点从属面积（足尺）。
输入：R25.1-13 三库测点统一坐标 csv（只读，sha 前16位 b154ee35903e4ffe，R25.3 冻结登记）+ xfer/manifest_sel.tsv。
做法：屋面平面投影矩形内 0.05 m 网格，每格归最近测点（= 截断到矩形的 Voronoi）。
矩形：无檐库取 x 沿长边 ±max(B,D)/2、y ±min(B,D)/2（核过 g080200 测点 ±7、间距 2 与 B=16 一致）；
有檐库挑檐尺寸未在 csv 中，取测点包络外扩半个中位间距（假设，M2 报告标明）。
真实面积 = 平面面积 / cos(坡角)。只算 ROOF，墙与挑檐底另议。
输出 m2_tributary_area.csv：lib,case,tap,x_fs,y_fs,A_plan,A_true,rect_rule
"""
import csv, sys, math, numpy as np
from scipy.spatial import cKDTree
coords, manifest, out = sys.argv[1:4]
sel = sorted({(l.split('\t')[0], l.split('\t')[1].split('/')[0]) for l in open(manifest) if l.strip()})
rows = [r for r in csv.DictReader(open(coords)) if r['face_type'] == 'ROOF']
w = csv.writer(open(out, 'w', newline='')); w.writerow(['lib','case','tap','x_fs','y_fs','A_plan','A_true','rect_rule'])
for lib, case in sel:
    t = [r for r in rows if r['lib'] == lib and r['case'] == case]
    if not t: print('MISSING', lib, case); continue
    xy = np.array([[float(r['x_fs']), float(r['y_fs'])] for r in t]); B, D = float(t[0]['B']), float(t[0]['D'])
    pitch = float(t[0]['pitch'])
    if lib == 'noeaves':
        x0, x1, y0, y1 = -max(B,D)/2, max(B,D)/2, -min(B,D)/2, min(B,D)/2; rule = 'B×D(x沿长边)'
    else:
        hx = np.median(np.diff(np.unique(xy[:,0])))/2; hy = np.median(np.diff(np.unique(xy[:,1])))/2
        x0, x1, y0, y1 = xy[:,0].min()-hx, xy[:,0].max()+hx, xy[:,1].min()-hy, xy[:,1].max()+hy; rule = 'envelope+half_spacing(假设)'
    assert xy[:,0].min() >= x0-1e-6 and xy[:,0].max() <= x1+1e-6 and xy[:,1].min() >= y0-1e-6 and xy[:,1].max() <= y1+1e-6, (lib, case)
    g = 0.05; gx = np.arange(x0+g/2, x1, g); gy = np.arange(y0+g/2, y1, g)
    G = np.stack(np.meshgrid(gx, gy), -1).reshape(-1, 2)
    idx = cKDTree(xy).query(G)[1]; A = np.bincount(idx, minlength=len(t)) * g * g
    c = math.cos(math.radians(pitch))
    for r, a in zip(t, A): w.writerow([lib, case, r['tap'], r['x_fs'], r['y_fs'], round(a,4), round(a/c,4), rule])
    print(lib, case, len(t), 'sumA_plan=%.2f rect=%.2f' % (A.sum(), (x1-x0)*(y1-y0)))
