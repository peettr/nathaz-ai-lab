"""Recover one PySR run whose search finished (hall_of_fame saved 03:14) but whose post-processing hung.
Loads the saved run directory with PySRRegressor.from_file, applies the SAME selection rule as lc_pysr_run.py,
and computes canon() with a 300 s timeout (timeout -> canon='TIMEOUT', counted as not isomorphic to any seed;
rule added 11-15 after the hang, before reading any learning-curve result).
Usage: python lc_fill_from_hof.py <args.json> ds target N seed run_dir out_dir"""
import json, os, signal, sys
from lc_common import CFG, load, split, val_cases, grid, plausible
from common import rmse, n_consts, canon, loose_sig

class TO(Exception): pass
def _h(*a): raise TO()

def guarded(fn, x, sec=300):
    signal.signal(signal.SIGALRM, _h); signal.alarm(sec)
    try: return fn(x)
    except TO: return 'TIMEOUT'
    finally: signal.alarm(0)

def main(argf, ds, tname, N, seed, run_dir, out):
    from pysr import PySRRegressor
    a = json.load(open(argf)); N, seed = int(N), int(seed); cfg = CFG[ds]; col = cfg['targets'][tname]; F = cfg['feats']
    df = load(ds, a); tr, te, _ = split(df, ds, N); vc = val_cases(tr); val = tr[tr.case.isin(vc)]
    m = PySRRegressor.from_file(run_directory=run_dir); eqs = m.equations_
    rv = [rmse(m.predict(val[F], index=i), val[col]) for i in range(len(eqs))]; best = min(rv)
    i = min([k for k in range(len(eqs)) if rv[k] <= 1.02 * best], key=lambda k: int(eqs.complexity[k]))
    ok, msg = plausible(m.predict(grid(ds)[F], index=i), tname)
    e = eqs.sympy_format[i]
    res = dict(ds=ds, target=tname, N=N, seed=seed, recovered_from=run_dir, equation=str(eqs.equation[i]), sympy=str(e),
               complexity=int(eqs.complexity[i]), rmse_test=rmse(m.predict(te[F], index=i), te[col]), n_consts=n_consts(e),
               canon=guarded(canon, e), loose=guarded(lambda z: list(map(str, loose_sig(z))), e), plausible=ok, grid=msg)
    if res['loose'] == 'TIMEOUT': res['loose'] = ['TIMEOUT']
    tag = f'{ds}_{tname}_N{N}_s{seed}'
    json.dump(res, open(os.path.join(out, f'{tag}.json'), 'w'), indent=1)
    print(tag, 'test', round(res['rmse_test'], 4), 'consts', res['n_consts'], 'canon_timeout', res['canon'] == 'TIMEOUT', res['equation'], flush=True)

if __name__ == '__main__':
    main(*sys.argv[1:8])
