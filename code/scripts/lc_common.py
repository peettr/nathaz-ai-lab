"""L26.3 learning curve (Liang Hu 11-14). Shared data/split/baseline/library code.
Datasets: hr = TPU high-rise isolated (22 cases); lr = TPU low-rise no-eaves, gable roofs,
development group only (H0 != 12; sealed H0 = 12 group is never opened)."""
import csv, io, itertools, math, zipfile
import numpy as np
import pandas as pd
from common import load as load_hr, rmse

ANG = ['c1', 's1', 'c2', 's2']
CFG = {
    'hr': dict(feats=['xh', 'xr', 'xa'] + ANG, geo=('xh', 'xr', 'xa'),
               targets={'mean_f3': 'mean_f3_aw', 'std_f3': 'std_f3_aw'}, Ns=(8, 12, 17, 22)),
    'lr': dict(feats=['xh', 'xd', 'xp'] + ANG, geo=('xh', 'xd', 'xp'),
               targets={'rw_mean': 'rw_mean', 'rw_std': 'rw_std'}, Ns=(8, 12, 17, 22, 48)),
}
CHAIN_SEED = 2026
STATS_SHA = '7bff3edaef3b1a33c6623635caa2661e4e716203f1c4e99e62bf4ba6a37b3b92'


def add_angles(df):
    t = np.deg2rad(df.theta.values)
    df['c1'], df['s1'], df['c2'], df['s2'] = np.cos(t), np.sin(t), np.cos(2 * t), np.sin(2 * t)
    return df


def load_lr(stats, coords):
    """Roof taps of gable development buildings; windward-third zone s < -1/3 with
    s = u cos(theta) + v sin(theta) (R25.1-13 convention). Equal tap weights."""
    import hashlib
    if hashlib.sha256(open(stats, 'rb').read()).hexdigest() != STATS_SHA:
        raise RuntimeError('stats hash mismatch')
    bycase = {}
    for r in csv.DictReader(open(coords, newline='')):
        if r['lib'] != 'noeaves' or r['face_type'] != 'ROOF' or r['roof'] != 'gable roof':
            continue
        if float(r['H0']) == 12.0:          # sealed group: filtered before any Cp member is opened
            continue
        bycase.setdefault(r['case'], []).append(r)
    if len(bycase) != 72:
        raise RuntimeError(f'expected 72 gable dev buildings, got {len(bycase)}')
    rows = []
    with zipfile.ZipFile(stats) as z:
        for case, taps in sorted(bycase.items()):
            idx = np.array([int(t['tap']) - 1 for t in taps])
            u = np.array([float(t['u']) for t in taps]); v = np.array([float(t['v']) for t in taps])
            g = {k: float(taps[0][k]) for k in ('pitch', 'H0', 'B', 'D')}
            for th in range(0, 91, 15):
                a = np.load(io.BytesIO(z.read(f'{case}_{th:03d}.npy')), allow_pickle=False)
                s = u * math.cos(math.radians(th)) + v * math.sin(math.radians(th))
                m = s < -1 / 3
                rows.append(dict(case=case, theta=th, xh=g['H0'] / g['B'], xd=g['D'] / g['B'], xp=g['pitch'] / 45.0,
                                 rw_mean=float(a[0, idx[m]].mean()), rw_std=float(a[1, idx[m]].mean()), n_taps=int(m.sum())))
    return add_angles(pd.DataFrame(rows))


def load(ds, args):
    return load_hr(args['hr_stats']) if ds == 'hr' else load_lr(args['lr_stats'], args['lr_coords'])


def split(df, ds, N):
    """Returns train, test. hr: test = all cases at theta 30-45 (scheme H2); training pool = 22 cases.
    lr: test = 24 fixed buildings (all directions); training pool = remaining 48.
    Training cases = first N of a seeded permutation of the pool (nested chain)."""
    cases = np.array(sorted(df.case.unique()))
    rng = np.random.default_rng(CHAIN_SEED)
    if ds == 'hr':
        test = df[df.theta.isin((30, 35, 40, 45))]
        pool = df[~df.theta.isin((30, 35, 40, 45))]
        order = rng.permutation(cases)
    else:
        perm = rng.permutation(cases); test_cases = set(perm[:24]); order = perm[24:]
        test = df[df.case.isin(test_cases)]; pool = df[~df.case.isin(test_cases)]
    train = pool[pool.case.isin(set(order[:N]))]
    return train.reset_index(drop=True), test.reset_index(drop=True), list(order[:N])


def val_cases(train, frac=0.2, seed=0):
    cases = np.array(sorted(train.case.unique()))
    return set(np.random.default_rng(seed).choice(cases, max(1, int(round(frac * len(cases)))), replace=False))


# ---- baselines (same two families as 10-19) ----
def design(df, terms):
    return np.column_stack([np.ones(len(df))] + [np.prod([df[f].values for f in t], axis=0) for t in terms])


def forward_stepwise(train, y, feats, kmax=20, nfold=5):
    allt = [(f,) for f in feats] + list(itertools.combinations_with_replacement(feats, 2))
    cases = np.array(sorted(train.case.unique())); rng = np.random.default_rng(0); rng.shuffle(cases)
    folds = np.array_split(cases, min(nfold, len(cases)))
    order, chosen = [], []
    for _ in range(min(kmax, len(allt))):
        best = None
        for t in allt:
            if t in chosen: continue
            X = design(train, chosen + [t]); b = np.linalg.lstsq(X, y, rcond=None)[0]; r = rmse(X @ b, y)
            if best is None or r < best[0]: best = (r, t)
        chosen.append(best[1]); order.append(list(chosen))
    cv = []
    for sel in order:
        se = 0.0; X = design(train, sel)
        for fc in folds:
            te = train.case.isin(fc).values
            b = np.linalg.lstsq(X[~te], y[~te], rcond=None)[0]; se += np.sum((X[te] @ b - y[te]) ** 2)
        cv.append(np.sqrt(se / len(y)))
    return order[int(np.argmin(cv))]


def powlaw(p, df, ds):
    c0, c1, c2, c3, c4, pe, qe, se = p
    ang = c0 + c1 * df.c1.values + c2 * df.s1.values + c3 * df.c2.values + c4 * df.s2.values
    if ds == 'hr':
        return ang * df.xh.values ** pe * df.xr.values ** qe * (df.xa.values / 0.2) ** se
    return ang * df.xh.values ** pe * df.xd.values ** qe * (1 + df.xp.values) ** se


def baselines(train, test, y, yt, ds):
    from scipy.optimize import least_squares
    feats = CFG[ds]['feats']
    sel = forward_stepwise(train, y, feats); b = np.linalg.lstsq(design(train, sel), y, rcond=None)[0]
    r_poly = rmse(design(test, sel) @ b, yt)
    p = least_squares(lambda q: powlaw(q, train, ds) - y, [float(np.mean(y))] + [0] * 7, max_nfev=20000).x
    r_pow = rmse(powlaw(p, test, ds), yt)
    best = 'poly' if r_poly <= r_pow else 'pow'
    return dict(poly_rmse=r_poly, poly_n=len(b), pow_rmse=r_pow, pow_n=8, best=best,
                best_rmse=min(r_poly, r_pow), best_n=len(b) if best == 'poly' else 8)


# ---- plausibility grid (same ranges as 10-19 definition) ----
def grid(ds):
    th = np.arange(0, 101 if ds == 'hr' else 91)
    if ds == 'hr':
        g = itertools.product(np.linspace(1, 6, 26), [1, 1.5, 2, 2.5, 3], [1 / 6, 0.25], th)
        df = pd.DataFrame(list(g), columns=['xh', 'xr', 'xa', 'theta'])
    else:
        g = itertools.product(np.linspace(0.25, 1.0, 16), [1, 1.5, 2, 2.5], np.linspace(0, 1, 11), th)
        df = pd.DataFrame(list(g), columns=['xh', 'xd', 'xp', 'theta'])
    return add_angles(df.astype(float))


def plausible(vals, target):
    v = np.asarray(vals, dtype=float)
    if not np.all(np.isfinite(v)): return False, 'non-finite'
    lo, hi = (-2.0, 1.2) if 'mean' in target else (0.0, 1.0)
    return bool(v.min() >= lo and v.max() <= hi), f'[{v.min():.3f}, {v.max():.3f}]'


# ---- SINDy library: {1,cos,sin,cos2,sin2} x {1, g1, 1/g1, ln g1, g2, 1/g2, g3} ----
def sindy_lib(df, ds):
    g1, g2, g3 = (df[k].values for k in CFG[ds]['geo'])
    th = [np.ones(len(df)), df.c1.values, df.s1.values, df.c2.values, df.s2.values]
    ge = [np.ones(len(df)), g1, 1 / g1, np.log(g1), g2, 1 / g2, g3]
    return np.column_stack([a * b for a in th for b in ge])
