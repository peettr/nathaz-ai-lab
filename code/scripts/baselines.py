"""L26.3 baselines: B-poly (forward stepwise, CV-chosen K) and B-pow; plus ASCE 7-22 table comparison.
Usage: python -I baselines.py stats.csv out_dir"""
import json, os, sys
import numpy as np
from common import *

def asce_leeward(LB):
    return np.interp(LB, [0, 1, 2, 4, 1e9], [-0.5, -0.5, -0.3, -0.2, -0.2])

def main(stats, out):
    os.makedirs(out, exist_ok=True)
    df = load(stats); res = {}
    for tname, col in TARGETS.items():
        for scheme in ('H1', 'H2'):
            tr, te = split(df, scheme); y, yt = tr[col].values, te[col].values
            sel, cv = forward_stepwise(tr, y)
            X = design(tr, sel); b = fit_ls(X, y)
            r_poly = rmse(design(te, sel) @ b, yt)
            p = fit_powlaw(tr, y); r_pow = rmse(powlaw(p, te), yt)
            best = 'poly' if r_poly <= r_pow else 'pow'
            res[f'{tname}_{scheme}'] = dict(
                n_train=len(tr), n_test=len(te),
                poly=dict(terms=[list(t) for t in sel], coef=b.tolist(), n_params=len(b), rmse_test=r_poly,
                          rmse_train=rmse(X @ b, y), cv=cv),
                pow=dict(params=p.tolist(), n_params=8, rmse_test=r_pow, rmse_train=rmse(powlaw(p, tr), y)),
                best=best, best_rmse=min(r_poly, r_pow),
                best_nparams=len(b) if best == 'poly' else 8,
                std_test=float(np.std(yt)))
            print(tname, scheme, 'poly', len(b), round(r_poly, 4), 'pow', round(r_pow, 4), 'std', round(float(np.std(yt)), 4), flush=True)
    # ASCE 7-22 Fig. 27.3-1 comparison (not part of criteria): leeward face at 0 deg and 90 deg
    rows = []
    for th, lb in ((0, None), (90, None)):
        sub = df[df.theta == th]
        for _, r in sub.iterrows():
            LB = r.D / r.B if th == 0 else r.B / r.D   # along-wind depth / across-wind breadth
            lee = r.mean_f3_aw if th == 0 else r.mean_f4_aw
            side = (r.mean_f2_aw + r.mean_f4_aw) / 2 if th == 0 else (r.mean_f1_aw + r.mean_f3_aw) / 2
            rows.append(dict(case=r.case, theta=th, LB=LB, tpu_leeward=lee, asce_leeward=float(asce_leeward(LB)),
                             tpu_side=side, asce_side=-0.7))
    res['asce_compare'] = rows
    json.dump(res, open(os.path.join(out, 'baselines.json'), 'w'), indent=1)

if __name__ == '__main__':
    main(*sys.argv[1:3])
