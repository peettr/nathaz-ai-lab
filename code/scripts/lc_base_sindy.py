"""Baselines + SINDy (v2 config: STLSQ, normalize_columns, threshold logspace(-3,3,61) by grouped 5-fold CV,
5 grouped bootstraps) for every dataset x target x N. Usage: python lc_base_sindy.py <args.json> <out_dir>"""
import collections, json, os, sys
import numpy as np
from pysindy.optimizers import STLSQ
from lc_common import CFG, load, split, baselines, sindy_lib, grid, plausible
from common import rmse

THRESH = np.logspace(-3, 3, 61)

def fit(X, y, thr):
    o = STLSQ(threshold=thr, alpha=1e-6, normalize_columns=True, max_iter=50); o.fit(X, y.reshape(-1, 1)); return o.coef_.ravel()

def cv_thr(tr, y, ds):
    cases = np.array(sorted(tr.case.unique())); rng = np.random.default_rng(0); rng.shuffle(cases)
    folds = np.array_split(cases, min(5, len(cases))); X = sindy_lib(tr, ds); out = []
    for thr in THRESH:
        se = 0.0
        for fc in folds:
            te = tr.case.isin(fc).values; c = fit(X[~te], y[~te], thr); se += np.sum((X[te] @ c - y[te]) ** 2)
        out.append(float(np.sqrt(se / len(y))))
    k = int(np.argmin(out)); return float(THRESH[k]), out

def main(argf, out):
    a = json.load(open(argf)); os.makedirs(out, exist_ok=True); res = {}
    for ds, cfg in CFG.items():
        df = load(ds, a)
        for tname, col in cfg['targets'].items():
            for N in cfg['Ns']:
                tr, te, cases = split(df, ds, N); y, yt = tr[col].values, te[col].values
                B = baselines(tr, te, y, yt, ds)
                thr, cvc = cv_thr(tr, y, ds); c = fit(sindy_lib(tr, ds), y, thr); nz = np.flatnonzero(c)
                ok, msg = plausible(sindy_lib(grid(ds), ds) @ c, tname)
                sups = []
                for b in range(5):
                    pick = np.random.default_rng(100 + b).choice(np.array(sorted(tr.case.unique())), tr.case.nunique(), replace=True)
                    idx = np.concatenate([np.flatnonzero(tr.case.values == k) for k in pick])
                    sups.append(tuple(np.flatnonzero(fit(sindy_lib(tr.iloc[idx], ds), y[idx], thr))))
                cnt = collections.Counter(sups)
                res[f'{ds}|{tname}|{N}'] = dict(ds=ds, target=tname, N=N, train_cases=[str(x) for x in cases],
                    n_train=len(tr), n_test=len(te), baseline=B,
                    sindy=dict(threshold=thr, thr_at_edge=bool(thr in (THRESH[0], THRESH[-1])), cv_curve=cvc,
                               n_terms=int(len(nz)), rmse_test=rmse(sindy_lib(te, ds) @ c, yt), plausible=ok, grid=msg,
                               boot_supports=[list(map(int, s)) for s in sups], boot_top=int(cnt.most_common(1)[0][1])))
                r = res[f'{ds}|{tname}|{N}']
                print(ds, tname, N, 'base', B['best'], round(B['best_rmse'], 4), 'sindy', round(r['sindy']['rmse_test'], 4), r['sindy']['n_terms'], 'boot', r['sindy']['boot_top'], flush=True)
    json.dump(res, open(os.path.join(out, 'base_sindy.json'), 'w'), indent=1)

if __name__ == '__main__':
    main(*sys.argv[1:3])
