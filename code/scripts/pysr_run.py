"""L26.3 one PySR run. Usage: python pysr_run.py stats.csv target scheme seed niter threads out_dir"""
import json, os, sys, time
import numpy as np
from common import *

def main(stats, tname, scheme, seed, niter, out):
    from pysr import PySRRegressor
    seed, niter = int(seed), int(niter)
    df = load(stats); col = TARGETS[tname]
    tr, te = split(df, scheme)
    vc = val_cases(tr)
    fit = tr[~tr.case.isin(vc)]; val = tr[tr.case.isin(vc)]
    tag = f'{tname}_{scheme}_s{seed}'
    odir = os.path.join(out, 'pysr_tmp', tag); os.makedirs(odir, exist_ok=True)
    m = PySRRegressor(niterations=niter, binary_operators=['+', '-', '*', '/'], unary_operators=['square', 'exp', 'cos'],
                      nested_constraints={'exp': {'exp': 0}, 'cos': {'cos': 0}}, maxsize=30,
                      random_state=seed, parallelism='multithreading', deterministic=False,
                      output_directory=odir, progress=False, verbosity=0)
    t0 = time.time()
    m.fit(fit[FEATS], fit[col].values)
    eqs = m.equations_
    rows = []
    for i in range(len(eqs)):
        f = lambda d, i=i: m.predict(d[FEATS], index=i)
        rows.append(dict(i=i, complexity=int(eqs.complexity[i]), loss=float(eqs.loss[i]), equation=str(eqs.equation[i]),
                         sympy=str(eqs.sympy_format[i]), rmse_val=rmse(f(val), val[col]), rmse_fit=rmse(f(fit), fit[col])))
    rv = np.array([r['rmse_val'] for r in rows]); best = rv.min()
    cand = [r for r in rows if r['rmse_val'] <= 1.02 * best]
    sel = min(cand, key=lambda r: r['complexity'])
    # refit-free evaluation on held-out set with the selected expression
    sel_i = sel['i']
    res = dict(target=tname, scheme=scheme, seed=seed, niter=niter, seconds=time.time() - t0,
               n_fit=len(fit), n_val=len(val), val_cases=sorted(vc), selected=sel,
               rmse_test=rmse(m.predict(te[FEATS], index=sel_i), te[col]),
               n_consts=n_consts(eqs.sympy_format[sel_i]), front=rows)
    ok, msg = plausible(lambda g: m.predict(g[FEATS], index=sel_i), tname)
    res['plausible'] = ok; res['plausible_msg'] = msg
    res['canon'] = canon(eqs.sympy_format[sel_i]); res['loose'] = list(map(str, loose_sig(eqs.sympy_format[sel_i])))
    json.dump(res, open(os.path.join(out, f'{tag}.json'), 'w'), indent=1)
    print(tag, 'test', round(res['rmse_test'], 4), 'consts', res['n_consts'], 'cx', sel['complexity'], sel['equation'], flush=True)

if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], a[1], a[2], a[3], a[4], a[6])
