"""One PySR run, config identical to J3 (3000 iters, ops + - * / square exp cos, maxsize 30,
nested constraints, 20% validation cases, select min val RMSE within 2% -> simplest).
Usage: python lc_pysr_run.py <args.json> ds target N seed out_dir"""
import json, os, sys, time
import numpy as np
from lc_common import CFG, load, split, val_cases, grid, plausible
from common import rmse, n_consts, canon, loose_sig

def main(argf, ds, tname, N, seed, out):
    from pysr import PySRRegressor
    a = json.load(open(argf)); N, seed = int(N), int(seed); cfg = CFG[ds]; col = cfg['targets'][tname]; F = cfg['feats']
    df = load(ds, a); tr, te, cases = split(df, ds, N)
    vc = val_cases(tr); fit, val = tr[~tr.case.isin(vc)], tr[tr.case.isin(vc)]
    tag = f'{ds}_{tname}_N{N}_s{seed}'; od = os.path.join(out, 'pysr_tmp', tag); os.makedirs(od, exist_ok=True)
    m = PySRRegressor(niterations=3000, binary_operators=['+', '-', '*', '/'], unary_operators=['square', 'exp', 'cos'],
                      nested_constraints={'exp': {'exp': 0}, 'cos': {'cos': 0}}, maxsize=30, random_state=seed,
                      parallelism='multithreading', deterministic=False, output_directory=od, progress=False, verbosity=0)
    t0 = time.time(); m.fit(fit[F], fit[col].values); eqs = m.equations_
    rv = [rmse(m.predict(val[F], index=i), val[col]) for i in range(len(eqs))]; best = min(rv)
    i = min([k for k in range(len(eqs)) if rv[k] <= 1.02 * best], key=lambda k: int(eqs.complexity[k]))
    ok, msg = plausible(m.predict(grid(ds)[F], index=i), tname)
    res = dict(ds=ds, target=tname, N=N, seed=seed, seconds=time.time() - t0, equation=str(eqs.equation[i]),
               sympy=str(eqs.sympy_format[i]), complexity=int(eqs.complexity[i]),
               rmse_test=rmse(m.predict(te[F], index=i), te[col]), n_consts=n_consts(eqs.sympy_format[i]),
               canon=canon(eqs.sympy_format[i]), loose=list(map(str, loose_sig(eqs.sympy_format[i]))), plausible=ok, grid=msg)
    json.dump(res, open(os.path.join(out, f'{tag}.json'), 'w'), indent=1)
    print(tag, 'test', round(res['rmse_test'], 4), 'consts', res['n_consts'], res['equation'], flush=True)

if __name__ == '__main__':
    main(*sys.argv[1:7])
