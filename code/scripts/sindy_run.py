"""L26.3 SINDy-style sparse regression (pre-registered 11-10, 05_Projects/L26.3_补充方案_SINDy_20261110.md).
Usage: python sindy_run.py stats.csv j3_fits_dir out_dir"""
import collections, glob, json, os, sys
import numpy as np
from pysindy.optimizers import STLSQ
from common import TARGETS, load, split, rmse, physical_grid

THETA = [('1', lambda d: np.ones(len(d))), ('cos', lambda d: d.c1.values), ('sin', lambda d: d.s1.values),
         ('cos2', lambda d: d.c2.values), ('sin2', lambda d: d.s2.values)]
GEOM = [('1', lambda d: np.ones(len(d))), ('xh', lambda d: d.xh.values), ('1/xh', lambda d: 1 / d.xh.values),
        ('ln_xh', lambda d: np.log(d.xh.values)), ('xr', lambda d: d.xr.values), ('1/xr', lambda d: 1 / d.xr.values),
        ('a', lambda d: d.xa.values)]
NAMES = [f'{t}*{g}' for t, _ in THETA for g, _ in GEOM]
THRESH = np.logspace(-3, 0, 31)


def lib(d):
    return np.column_stack([ft(d) * fg(d) for _, ft in THETA for _, fg in GEOM])


def fit(X, y, thr):
    opt = STLSQ(threshold=thr, alpha=1e-6, normalize_columns=True, max_iter=50)
    opt.fit(X, y.reshape(-1, 1))
    return opt.coef_.ravel()


def cv_threshold(tr, y, nfold=5):
    cases = np.array(sorted(tr.case.unique())); rng = np.random.default_rng(0); rng.shuffle(cases)
    folds = np.array_split(cases, nfold); X = lib(tr); best = None
    for thr in THRESH:
        se = 0.0
        for fc in folds:
            te = tr.case.isin(fc).values
            c = fit(X[~te], y[~te], thr); se += np.sum((X[te] @ c - y[te]) ** 2)
        r = np.sqrt(se / len(y))
        if best is None or r < best[0] - 1e-12: best = (r, thr)
    return best[1], best[0]


def main(stats, j3dir, out):
    os.makedirs(out, exist_ok=True)
    df = load(stats); B = json.load(open(os.path.join(j3dir, 'baselines.json')))
    rows, verdict = [], {}
    for t, col in TARGETS.items():
        res = {}
        for s in ('H1', 'H2'):
            tr, te = split(df, s); y = tr[col].values
            thr, cvr = cv_threshold(tr, y)
            c = fit(lib(tr), y, thr); nz = np.flatnonzero(c)
            r_te = rmse(lib(te) @ c, te[col].values)
            v = lib(physical_grid()) @ c
            lo, hi = (-2.0, 1.2) if t.startswith('mean') else (0.0, 1.0)
            plaus = bool(np.all(np.isfinite(v)) and v.min() >= lo and v.max() <= hi)
            cases = np.array(sorted(tr.case.unique())); supports = []
            for b in range(5):
                pick = np.random.default_rng(100 + b).choice(cases, len(cases), replace=True)
                idx = np.concatenate([np.flatnonzero(tr.case.values == k) for k in pick])
                cb = fit(lib(tr.iloc[idx]), y[idx], thr); supports.append(tuple(np.flatnonzero(cb)))
            top = collections.Counter(supports).most_common(1)[0][1]
            freq = collections.Counter(i for sup in supports for i in sup)
            loose = sum(1 for i in nz if freq[i] >= 4) / max(len(nz), 1)
            pys = sorted(json.load(open(f))['rmse_test'] for f in glob.glob(os.path.join(j3dir, f'{t}_{s}_s*.json')))
            b = B[f'{t}_{s}']
            res[s] = dict(threshold=float(thr), cv_rmse=float(cvr), n_terms=int(len(nz)),
                          terms={NAMES[i]: float(c[i]) for i in nz}, rmse_test=r_te,
                          ratio=r_te / b['best_rmse'], base_rmse=b['best_rmse'], base_n=b['best_nparams'],
                          nf=r_te <= 1.05 * b['best_rmse'], strict=r_te <= b['best_rmse'], nc=len(nz) <= b['best_nparams'],
                          plausible=plaus, grid_range=[float(v.min()), float(v.max())],
                          boot_top=int(top), stable=top >= 3, loose_frac=loose,
                          pysr_median=pys[len(pys) // 2] if pys else None)
            rows.append((t, s, res[s]))
        ok = all(res[s]['nf'] and res[s]['nc'] and res[s]['plausible'] and res[s]['stable'] for s in ('H1', 'H2'))
        verdict[t] = ok
    json.dump({f'{t}_{s}': r for t, s, r in rows}, open(os.path.join(out, 'sindy_results.json'), 'w'), indent=1)
    L = ['| 目标 | 留出 | 最佳基线 RMSE(参数) | SINDy RMSE(项数) | 比值 | 不劣1.05 | 严格1.00 | 项数 | 量纲 | 自助最多相同/5 | 宽松占比 | PySR3000中位 |', '|' + '---|' * 12]
    for t, s, r in rows:
        yn = lambda x: '是' if x else '否'
        L.append(f"| {t} | {s} | {r['base_rmse']:.4f}({r['base_n']}) | {r['rmse_test']:.4f}({r['n_terms']}) | {r['ratio']:.3f} | {yn(r['nf'])} | {yn(r['strict'])} | {yn(r['nc'])} | {yn(r['plausible'])} | {r['boot_top']} | {r['loose_frac']:.2f} | {r['pysr_median']:.4f} |")
    n = sum(verdict.values())
    L += ['', '目标量通过：' + '，'.join(f'{t} {"通过" if v else "不通过"}' for t, v in verdict.items()),
          f'通过 {n}/4 → {"值得用" if n >= 2 else "放弃"}（判据：≥2 个通过）']
    open(os.path.join(out, 'verdict_sindy.md'), 'w').write('\n'.join(L) + '\n'); print('\n'.join(L))
    for t, s, r in rows: print(t, s, r['terms'])


if __name__ == '__main__':
    main(*sys.argv[1:4])
