#!/usr/bin/env python3
"""L26.11 O-d (Liang Hu 11-13) two-mesh verdict, pre-registered 11-13 before any coarse run.
usage: analyze_c.py <coarse root containing M1/ M3/ (postProcessing or case/postProcessing)> <lyn_csv> <medium verdict json> <out_prefix>
Metric functions are copied verbatim from analyze_m.py (sha 24f82512...); windows identical (M1 151.5-606.1, M3 227.3-681.9).
G   = |R_medium(M1) - R_coarse(M1)|                      (10-24 definition, Delta_max on both meshes)
D_m = R_medium(M1) - R_medium(M3) (from medium json);  D_c = R_coarse(M1) - R_coarse(M3)
Order: (1) coarse data invalid -> invalid; (2) coarse baseline gate fails (E_St>0.15 or E_CD>0.20) -> 不判（网格分辨力不足：粗网格基线未达参照）;
(3) coarse halves D strictly opposite sign -> 不判; (4) sign(D_c)==sign(D_m) and |D_c|>G and |D_m|>G:
    both <0 -> 不成立（两套网格；限本配置）; both >0 and both > max(G,0.03) and >=3/4 better on both meshes -> 成立（两套网格）; else 不判;
(5) otherwise -> 不判（网格分辨力不足）.  Parallel 10-24 reading (4 quantities per A297): 不成立 if D<=G on both meshes or >=3 worse on both;
成立 if D>max(G,0.03) and >=3 better on both and halves consistent; meshes contradict -> 不判."""
import sys, os, glob, re, json
import numpy as np
root, lyn_csv, med_json, outp = sys.argv[1:5]
WIN = {'M1': (151.5, 606.1), 'M3': (227.3, 681.9)}
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
med = json.load(open(med_json))['results']
K = ('St', 'CD', 'Lr', 'U')
v = {}
if INVALID or 'M1' not in res or 'M3' not in res:
    v = {'verdict': '数据无效，不作物理判定：' + '; '.join(INVALID)}
else:
    Dm = med['M1']['full']['R'] - med['M3']['full']['R']
    Dc = {w: res['M1'][w]['R'] - res['M3'][w]['R'] for w in ('full', 'H1', 'H2')}
    G = abs(med['M1']['full']['R'] - res['M1']['full']['R'])
    bm = sum(med['M3']['full']['E'][k] < med['M1']['full']['E'][k] for k in K)
    wm = sum(med['M3']['full']['E'][k] > med['M1']['full']['E'][k] for k in K)
    bc = sum(res['M3']['full']['E'][k] < res['M1']['full']['E'][k] for k in K)
    wc = sum(res['M3']['full']['E'][k] > res['M1']['full']['E'][k] for k in K)
    base_c = res['M1']['full']['E']['St'] <= 0.15 and res['M1']['full']['E']['CD'] <= 0.20
    halves_c = not (Dc['H1'] * Dc['H2'] < 0)
    D = Dc['full']
    if not base_c: verdict = '不判（网格分辨力不足：粗网格基线未达参照）'
    elif not halves_c: verdict = '不判（粗网格前后两半 D 符号相反）'
    elif np.sign(D) == np.sign(Dm) and abs(D) > G and abs(Dm) > G:
        if D < 0 and Dm < 0: verdict = '不成立（两套网格；限本配置）'
        elif D > max(G, 0.03) and Dm > max(G, 0.03) and bc >= 3 and bm >= 3: verdict = '成立（两套网格）'
        else: verdict = '不判（两套网格同号且超出 G，但未满足成立条件）'
    else: verdict = '不判（网格分辨力不足）'
    if (Dm <= G and D <= G) or (wm >= 3 and wc >= 3): orig = '不成立（原判据读法，4 量）'
    elif Dm > max(G, 0.03) and D > max(G, 0.03) and bm >= 3 and bc >= 3 and halves_c: orig = '成立（原判据读法，4 量）'
    else: orig = '不判（原判据读法：两套网格结论不一致）'
    v = {'G': G, 'D_medium': Dm, 'D_coarse': Dc, 'R_coarse': {r: res[r]['full']['R'] for r in res},
         'better_medium': int(bm), 'better_coarse': int(bc), 'worse_coarse': int(wc),
         'coarse_baseline_ok': bool(base_c), 'coarse_halves_consistent': bool(halves_c),
         'verdict': verdict, 'verdict_original_reading': orig}
json.dump({'results_coarse': res, 'verdict': v}, open(outp + '.json', 'w'), indent=1, default=float)
print(json.dumps({'verdict': v}, indent=1, default=float, ensure_ascii=False))
