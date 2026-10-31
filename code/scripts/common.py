"""L26.3 shared definitions (frozen 10-19 17:55 with the criteria on the project page)."""
import itertools
import numpy as np
import pandas as pd

TARGETS = {'mean_f1': 'mean_f1_aw', 'std_f1': 'std_f1_aw', 'mean_f3': 'mean_f3_aw', 'std_f3': 'std_f3_aw'}
FEATS = ['xh', 'xr', 'xa', 'c1', 's1', 'c2', 's2']
H2_THETAS = (30, 35, 40, 45)
SEEDS = (11, 22, 33, 44, 55)


def load(stats_csv):
    df = pd.read_csv(stats_csv)
    df['xh'] = df.H / np.minimum(df.B, df.D)
    df['xr'] = df.B / df.D
    df['xa'] = df.alpha
    t = np.deg2rad(df.theta)
    df['c1'], df['s1'], df['c2'], df['s2'] = np.cos(t), np.sin(t), np.cos(2 * t), np.sin(2 * t)
    return df


def split(df, scheme):
    if scheme == 'H1':
        test = np.isclose(df.xh, 5)
    elif scheme == 'H2':
        test = df.theta.isin(H2_THETAS)
    else:
        raise ValueError(scheme)
    return df[~test].reset_index(drop=True), df[test].reset_index(drop=True)


def val_cases(train, frac=0.2, seed=0):
    cases = np.array(sorted(train.case.unique()))
    rng = np.random.default_rng(seed)
    return set(rng.choice(cases, max(1, int(round(frac * len(cases)))), replace=False))


def rmse(a, b):
    return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))


# ---------- baselines ----------
def poly_terms():
    lin = [(f,) for f in FEATS]
    quad = list(itertools.combinations_with_replacement(FEATS, 2))
    return lin + quad


def design(df, terms):
    cols = [np.ones(len(df))] + [np.prod([df[f].values for f in t], axis=0) for t in terms]
    return np.column_stack(cols)


def fit_ls(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def forward_stepwise(train, y, kmax=20, nfold=5):
    """Greedy forward selection; K chosen by case-grouped CV on the training set only."""
    terms_all = poly_terms()
    cases = np.array(sorted(train.case.unique()))
    rng = np.random.default_rng(0); rng.shuffle(cases)
    folds = np.array_split(cases, nfold)
    order, chosen = [], []
    for _ in range(kmax):
        best = None
        for t in terms_all:
            if t in chosen: continue
            X = design(train, chosen + [t]); r = rmse(X @ fit_ls(X, y), y)
            if best is None or r < best[0]: best = (r, t)
        chosen.append(best[1]); order.append(list(chosen))
    cv = []
    for sel in order:
        err = []
        for fcases in folds:
            te = train.case.isin(fcases).values
            X = design(train, sel)
            b = fit_ls(X[~te], y[~te]); err.append(np.mean((X[te] @ b - y[te]) ** 2) * te.sum())
        cv.append(np.sqrt(np.sum(err) / len(y)))
    k = int(np.argmin(cv))
    return order[k], cv


def powlaw(p, df):
    c0, c1, c2, c3, c4, pe, qe, se = p
    return (c0 + c1 * df.c1 + c2 * df.s1 + c3 * df.c2 + c4 * df.s2).values * df.xh.values ** pe * df.xr.values ** qe * (df.xa.values / 0.2) ** se


def fit_powlaw(train, y):
    from scipy.optimize import least_squares
    p0 = [float(np.mean(y)), 0, 0, 0, 0, 0, 0, 0]
    r = least_squares(lambda p: powlaw(p, train) - y, p0, max_nfev=20000)
    return r.x


# ---------- formula analysis ----------
def n_consts(expr):
    import sympy as sp
    return sum(1 for a in expr.atoms(sp.Float))


def canon(expr):
    import sympy as sp
    c = sp.Symbol('C')
    e = sp.simplify(expr)
    e = e.xreplace({a: c for a in e.atoms(sp.Float)})
    e = e.xreplace({a: c for a in e.atoms(sp.Rational) if a not in (sp.Integer(1), sp.Integer(-1), sp.Integer(2), sp.Rational(1, 2))})
    return sp.srepr(sp.simplify(e))


def loose_sig(expr):
    import sympy as sp
    e = sp.simplify(expr)
    feats = tuple(sorted(str(s) for s in e.free_symbols))
    nterm = len(sp.Add.make_args(e))
    return feats, nterm


def physical_grid():
    xh = np.linspace(1, 6, 26); xr = np.array([1, 1.5, 2, 2.5, 3]); xa = np.array([1 / 6, 0.25]); th = np.arange(0, 101)
    g = np.array(list(itertools.product(xh, xr, xa, th)), dtype=float)
    df = pd.DataFrame(g, columns=['xh', 'xr', 'xa', 'theta'])
    t = np.deg2rad(df.theta)
    df['c1'], df['s1'], df['c2'], df['s2'] = np.cos(t), np.sin(t), np.cos(2 * t), np.sin(2 * t)
    return df


def plausible(fun, target):
    g = physical_grid()
    with np.errstate(all='ignore'):
        v = np.asarray(fun(g), dtype=float) * np.ones(len(g))
    if not np.all(np.isfinite(v)): return False, 'non-finite'
    lo, hi = (-2.0, 1.2) if target.startswith('mean') else (0.0, 1.0)
    ok = bool(v.min() >= lo and v.max() <= hi)
    return ok, f'range [{v.min():.3f}, {v.max():.3f}] vs [{lo}, {hi}]'
