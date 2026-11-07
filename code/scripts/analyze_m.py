#!/usr/bin/env python3
"""L26.11 step 2 criterion evaluation (pre-registered 10-26, Liang Hu A297).
usage: analyze_m.py <dir containing M1/ M2/ M3/ each with postProcessing/> <lyn_centreline_csv> <out_prefix>
Quantities (k): St, C_D, L_r (from rear face), centreline mean U at the 21 Lyn points x/H=1..4.
Reference (ERCOFTAC Case 043, Lyn data): St=0.132, C_D=2.1, L_r=0.885 (U=0 at x/H=1.385 from centre), U(x) from csv.
E_St=|St-0.132|/0.132; E_CD=|CD-2.1|/2.1; E_Lr=|Lr-0.885|/0.885; E_U=RMSE_i(U_sim(x_i)-U_exp(x_i)) (U_inf=1).
R = mean of the 4 E_k.  D = R(M1 Δmax) - R(M3 Δ_R).  Windows: M1 [151.5,606.1], M2/M3 [227.3,681.9]; halves split at mid-window.
Extra (not in verdict): R(M3)-R(M2); Cl_rms vs Rodi 1997 Table 1 LES range 1.15-1.79."""
import sys, os, glob, re, json
import numpy as np
root, lyn_csv, outp = sys.argv[1:4]
WIN = {'M1': (151.5, 606.1), 'M2': (227.3, 681.9), 'M3': (227.3, 681.9)}
REF = {'St': 0.132, 'CD': 2.1, 'Lr': 0.885}
lyn = np.loadtxt(lyn_csv, delimiter=',', skiprows=1)
lx, lu = lyn[:, 0], lyn[:, 1]

def pp(run):   # 10-26 review c5f7676e: accept <root>/<run>/postProcessing or <root>/<run>/case/postProcessing
    for d in (f'{root}/{run}/postProcessing', f'{root}/{run}/case/postProcessing'):
        if os.path.isdir(d): return d
    return None

INVALID = []   # 10-26 review c5f7676e: data-validity failures stop the physical verdict

def load_forces(run):
    rows = []
    for f in sorted(glob.glob(f'{pp(run)}/forceCoeffs1/*/coefficient.dat')):
        h = [l for l in open(f) if l.startswith('#')][-1][1:].split('\t'); h = [c.strip() for c in h]
        d = np.loadtxt(f, comments='#')
        rows.append(d[:, [0, h.index('Cd'), h.index('Cl')]])
    a = np.vstack(rows); a = a[np.argsort(a[:, 0])]
    _, idx = np.unique(a[:, 0], return_index=True); return a[idx]

def load_probes(run):
    pos, rows = None, []
    for f in sorted(glob.glob(f'{pp(run)}/centrelineProbes/*/U')):
        p = []
        for l in open(f):
            if l.startswith('# Probe'):
                p.append([float(v) for v in re.search(r'\(([^)]*)\)', l).group(1).split()])
            elif l.startswith('#') or not l.strip():
                continue
            else:
                t = float(l.split()[0])
                vecs = re.findall(r'\(([^)]*)\)', l)
                rows.append([t] + [float(v.split()[0]) for v in vecs])   # streamwise component only
        if pos is not None and (len(p) != len(pos) or not np.allclose(np.array(p), pos)):
            INVALID.append(f'{run}: probe positions differ between files')
        pos = np.array(p)
    a = np.array(rows); a = a[np.argsort(a[:, 0])]
    _, idx = np.unique(a[:, 0], return_index=True); return pos, a[idx]

def strouhal(t, cl):
    dt = np.median(np.diff(t)); x = (cl - cl.mean()) * np.hanning(len(cl))
    n = 1 << int(np.ceil(np.log2(len(x) * 8)))
    F = np.abs(np.fft.rfft(x, n)); f = np.fft.rfftfreq(n, dt)
    m = (f > 0.05) & (f < 0.5); return float(f[m][np.argmax(F[m])])

def metrics(run, t0, t1):
    fc = load_forces(run); m = (fc[:, 0] > t0) & (fc[:, 0] <= t1)
    t, cd, cl = fc[m, 0], fc[m, 1], fc[m, 2]
    tag = f'{run}[{t0},{t1}]'
    if len(t) < 2 or t[0] > t0 + 0.01 or t[-1] < t1 - 0.01: INVALID.append(f'{tag}: forces do not cover window ({t[0] if len(t) else None}-{t[-1] if len(t) else None})')
    elif np.max(np.diff(t)) > 1.5 * np.median(np.diff(t)): INVALID.append(f'{tag}: gap in forces (max dt {np.max(np.diff(t)):.4g})')
    St = strouhal(t, cl)
    pos, pr = load_probes(run); mp = (pr[:, 0] > t0) & (pr[:, 0] <= t1)
    tp = pr[mp, 0]
    if len(tp) < 2 or tp[0] > t0 + 0.2 or tp[-1] < t1 - 0.2: INVALID.append(f'{tag}: probes do not cover window')
    elif np.max(np.diff(tp)) > 1.5 * np.median(np.diff(tp)): INVALID.append(f'{tag}: gap in probes')
    umean = pr[mp, 1:].mean(axis=0)
    xs = np.unique(np.round(pos[:, 0], 4))
    ux = np.array([umean[np.isclose(pos[:, 0], x)].mean() for x in xs])       # spanwise average
    Lr = None
    for i in range(len(xs) - 1):
        if ux[i] < 0 <= ux[i + 1]:
            Lr = float(xs[i] + (0 - ux[i]) * (xs[i + 1] - xs[i]) / (ux[i + 1] - ux[i]) - 0.5); break
    usim = np.interp(lx, xs, ux)
    E = {'St': abs(St - REF['St']) / REF['St'], 'CD': abs(cd.mean() - REF['CD']) / REF['CD'],
         'Lr': (abs(Lr - REF['Lr']) / REF['Lr']) if Lr is not None else float('nan'),
         'U': float(np.sqrt(np.mean((usim - lu) ** 2)))}
    if Lr is None: INVALID.append(f'{tag}: no negative-to-positive zero crossing, L_r undefined')
    if not all(np.isfinite(list(E.values()))): INVALID.append(f'{tag}: non-finite error term {E}')
    return {'window': [t0, t1], 'data_span': [float(t[0]), float(t[-1])] if len(t) else None, 'cycles_in_data': St * (t[-1] - t[0]) if len(t) else None, 'n_force': int(m.sum()), 'n_probe': int(mp.sum()),
            'St': St, 'cycles_in_window': St * (t1 - t0), 'CD': float(cd.mean()), 'Cl_rms': float(cl.std()),
            'Lr_rear': Lr, 'E': E, 'R': float(np.mean(list(E.values())))}

res = {}
for run, (a, b) in WIN.items():
    if pp(run) is None: INVALID.append(f'{run}: postProcessing not found'); continue
    mid = 0.5 * (a + b)
    try:
        res[run] = {'full': metrics(run, a, b), 'H1': metrics(run, a, mid), 'H2': metrics(run, mid, b)}
    except Exception as e:
        INVALID.append(f'{run}: metrics failed ({type(e).__name__}: {e})')

v = {}
if 'M1' not in res or 'M3' not in res: v = {'verdict': '数据无效，不作物理判定：' + '; '.join(INVALID)}
else:
    D = {w: res['M1'][w]['R'] - res['M3'][w]['R'] for w in ('full', 'H1', 'H2')}
    better = {k: bool(res['M3']['full']['E'][k] < res['M1']['full']['E'][k]) for k in ('St', 'CD', 'Lr', 'U')}
    worse = {k: bool(res['M3']['full']['E'][k] > res['M1']['full']['E'][k]) for k in ('St', 'CD', 'Lr', 'U')}
    base_ok = res['M1']['full']['E']['St'] <= 0.15 and res['M1']['full']['E']['CD'] <= 0.20
    halves_ok = not (D['H1'] * D['H2'] < 0)   # 10-26 review c5f7676e: 'opposite sign' = strictly one positive, one negative
    cyc_ok = all(res[r]['full']['cycles_in_window'] >= 60 for r in res)
    if INVALID: verdict = '数据无效，不作物理判定：' + '; '.join(INVALID)
    elif not base_ok: verdict = '不判（基线 Δmax 的 St 误差 >15% 或 C_D 误差 >20%）'
    elif not halves_ok: verdict = '不判（前后两半 D 符号相反）'
    elif D['full'] > 0.03 and sum(better.values()) >= 3: verdict = '成立（单网格读法；G 无法计算）'
    elif D['full'] <= 0 or sum(worse.values()) >= 3: verdict = '不成立（限本配置；单网格读法）'
    else: verdict = '不判（未满足成立或不成立条件）'
    v = {'D': D, 'better_count': int(sum(better.values())), 'worse_count': int(sum(worse.values())),
         'better': better, 'baseline_ok': bool(base_ok), 'halves_sign_consistent': bool(halves_ok),
         'all_windows_ge_60_cycles': bool(cyc_ok), 'invalid': INVALID, 'verdict': verdict,
         'extra_R_M3_minus_M2': (res['M3']['full']['R'] - res['M2']['full']['R']) if 'M2' in res else None,
         'extra_Cl_rms_vs_Rodi_LES_range_1.15_1.79': {r: res[r]['full']['Cl_rms'] for r in res}}
json.dump({'results': res, 'verdict': v}, open(outp + '.json', 'w'), indent=1, default=float)
print(json.dumps({'verdict': v}, indent=1, default=float))
