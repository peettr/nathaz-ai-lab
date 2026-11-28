#!/usr/bin/env python3
"""R50.2 两档版门 B（EXPERIMENT_CARD_two.md ④，11-26 21:25 写定）：Roache 1994 两档 GCI，F_s=3，假设阶 p=1（判据），p=2 只报。读 VTK_BASE_6000 与 J_P1_<档>.json。原注（三档版）：L22.11 clean 门 B（卡 ④，11-25 21:10 写定）：基准平均量三档 GCI（Celik et al. 2008 式 1–5，非等比隐式 3a–c）。
用法：gateB.py <gateA.json> <粗目录> <中目录> <细目录> <输出json>；各目录含 VTK_0.0001/（xneg xpos yneg ypos roof ground 的 p、yPlus、wallShearStress）与 J_base_<档>.json。
主量：屋面、迎风(xneg)、背风(xpos)、两侧(yneg+ypos) 面积平均 Cp；测点 RMSE=√(J/180)；屋面中线再附长度 L_R。只报：地面中线尾流回流长度 L_W、y+ 中位与 30–300 占比。"""
import sys, re, glob, json, math, numpy as np
r21_in, dm, df, out = sys.argv[1:5]; r21 = float(r21_in)
U = 9.929988929927756
def arr(x, name):
    m = re.search(r"<DataArray[^>]*Name=[\"']%s[\"'][^>]*>(.*?)</DataArray>" % re.escape(name), x, re.S); return np.array(m.group(1).split(), float)
def read(p, fields):
    x = open(p).read(); C = []; A = []; F = {f: [] for f in fields}
    for pc in x.split('<Piece')[1:]:
        pts = np.array(re.search(r"<Points>\s*<DataArray[^>]*>(.*?)</DataArray>", pc, re.S).group(1).split(), float).reshape(-1, 3)
        con = arr(pc, 'connectivity').astype(int); off = arr(pc, 'offsets').astype(int); st = np.r_[0, off[:-1]]
        vals = {f: arr(pc, f) for f in fields}
        for f in fields:
            if len(vals[f]) == 3 * len(off): vals[f] = vals[f].reshape(-1, 3)
        for i, (a, b) in enumerate(zip(st, off)):
            q = pts[con[a:b]]; ar = 0.; cw = np.zeros(3)
            for j in range(1, len(q) - 1):
                t = .5 * np.linalg.norm(np.cross(q[j] - q[0], q[j + 1] - q[0])); ar += t; cw += t * (q[0] + q[j] + q[j + 1]) / 3
            C.append(cw / ar); A.append(ar)
            for f in fields: F[f].append(vals[f][i])
    return np.array(C), np.array(A), {f: np.array(v) for f, v in F.items()}
def patch(d, pa, fields):
    fs = sorted(glob.glob(f'{d}/VTK_BASE_6000/**/{pa}.vtp', recursive=True)); assert len(fs) == 1, (pa, fs); return read(fs[0], fields)
def crossing(x, tx, s0, x0):
    """沿 x 升序，从 x0 起找 τx 由「反向」(sign≠s0) 转为「正向」的第一个位置（线性插值）。返回 (状态, x)。"""
    m = x >= x0; x = x[m]; tx = tx[m]; fwd = np.sign(tx) == s0
    if len(x) == 0: return 'no_data', None
    if fwd.all(): return 'no_reverse', None
    i0 = np.argmax(~fwd)
    for i in range(i0 + 1, len(x)):
        if fwd[i] and not fwd[i - 1]:
            return 'reattach', float(x[i - 1] + (x[i] - x[i - 1]) * (0 - tx[i - 1]) / (tx[i] - tx[i - 1]))
    return 'no_reattach', None
def centerline(C, tau):
    ay = np.abs(C[:, 1]); m = ay <= ay.min() + 1e-3; xs = np.round(C[m, 0], 4); tx = tau[m, 0]
    ux = np.unique(xs); return ux, np.array([tx[xs == u].mean() for u in ux])
def wmed(v, a):
    o = np.argsort(v); c = np.cumsum(a[o]) / a.sum(); return float(v[o][np.searchsorted(c, .5)])
def grade(d, g):
    r = {}
    cp = {}
    for pa in ('xneg', 'xpos', 'yneg', 'ypos', 'roof'):
        C, A, F = patch(d, pa, ['p', 'yPlus', 'wallShearStress']); cp[pa] = (C, A, F)
    mean = lambda pas: float(sum((cp[p][1] * cp[p][2]['p']).sum() for p in pas) / sum(cp[p][1].sum() for p in pas) * 2 / U ** 2)
    r['Cp_roof'] = mean(['roof']); r['Cp_windward'] = mean(['xneg']); r['Cp_leeward'] = mean(['xpos']); r['Cp_sides'] = mean(['yneg', 'ypos'])
    J = json.load(open(f'{d}/J_P1_{g}.json'))['endpoints']['BASE_6000']['J']; r['RMSE'] = math.sqrt(J / 180); r['J_BASE'] = J
    Cg, Ag, Fg = patch(d, 'ground', ['wallShearStress'])
    up = (Cg[:, 0] >= -40) & (Cg[:, 0] <= -20) & (np.abs(Cg[:, 1]) <= 10); s0 = float(np.sign(Fg['wallShearStress'][up, 0].mean())); r['sign_forward'] = s0
    x, tx = centerline(cp['roof'][0], cp['roof'][2]['wallShearStress']); st, xr = crossing(x, tx, s0, -8.0)
    r['L_R_state'] = st; r['L_R'] = (xr + 8.0) if xr is not None else None
    x, tx = centerline(Cg, Fg['wallShearStress']); st, xw = crossing(x, tx, s0, 8.0)
    r['L_W_state'] = st; r['L_W'] = (xw - 8.0) if xw is not None else None
    for grp, pas in (('walls', ['xneg', 'xpos', 'yneg', 'ypos']), ('roof', ['roof'])):
        A = np.concatenate([cp[p][1] for p in pas]); V = np.concatenate([cp[p][2]['yPlus'] for p in pas])
        r[f'yplus_{grp}_median'] = wmed(V, A); r[f'yplus_{grp}_30_300'] = float(A[(V >= 30) & (V <= 300)].sum() / A.sum())
    return r
G = {'medium': grade(dm, 'two_medium'), 'fine': grade(df, 'two_fine')}
TH = {'Cp_roof': .05, 'Cp_windward': .05, 'Cp_leeward': .05, 'Cp_sides': .05, 'RMSE': .05, 'L_R': .10}
res = {'r21': r21, 'Fs': 3, 'grades': G, 'gci': {}}; ok = True
for k, th in TH.items():
    f1, f2 = G['fine'][k], G['medium'][k]
    if k == 'L_R' and (f1 is None or f2 is None):
        st = (G['medium']['L_R_state'], G['fine']['L_R_state'])
        o = {'kind': 'both_no_reattach' if st == ('no_reattach', 'no_reattach') else 'inconsistent', 'states': st}
        o['pass'] = o['kind'] == 'both_no_reattach'; res['gci'][k] = o; ok &= o['pass']; continue
    o = {'phi_medium': f2, 'phi_fine': f1, 'threshold': th}
    if abs(f1 - f2) < 1e-4: o.update(kind='near_zero', pass_=True)
    e = abs((f1 - f2) / f1); o['e'] = e
    o['GCI_p1'] = 3 * e / (r21 ** 1 - 1); o['GCI_p2'] = 3 * e / (r21 ** 2 - 1)
    o['pass'] = bool(o.pop('pass_', False) or o['GCI_p1'] <= th); res['gci'][k] = o; ok &= o['pass']
res['pass'] = bool(ok)
json.dump(res, open(out, 'w'), indent=1); print(json.dumps(res['gci'], indent=1)); print('GATE_B2', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 5)
