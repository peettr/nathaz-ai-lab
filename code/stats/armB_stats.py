"""L26.22 arm B statistics, written by Lead 11-13 BEFORE any method-G scoring-set result exists.
Definitions follow L30.1f preregistration v2 §2 and the L30.1f Lead script q1_analysis.py (sha256 cea0ee84...),
adapted to the actual field names of L30.1f scoring_run/results.jsonl ('e') and f_final.jsonl (f_u,f_I,f_L).
 S(case) = mean_k max(e_k - f_k, 0)/scale_k, scale = (5%, 10%, 20%), e = official best-round errors.
 Per-object S = mean over events of (mean over seeds).
 Main comparison (plan v1.2 §2.2): G vs A2 (GCA), two-sided Wilcoxon signed-rank over 24 objects.
  'G 优于 A2'  : median (S_A2-S_G)/S_A2 >= 20%, p < 0.01, G better on >= 18/24 objects.
  'A2 优于 G'  : mirror.
  '无差别'     : |median rel| < 5% and 90% bootstrap CI (5000, seed 0) within ±10%.
  else '不判'.
 Descriptive (no verdict): G vs A3, G vs A4, median S of each; G last-round S if field 'last_e' present.
 Completeness check: G must have 24 objects x 12 events x 3 seeds rows with official_valid; missing -> report, no verdict.
Usage: python3 armB_stats.py <L30.1f results.jsonl> <f_final.jsonl> <G results.jsonl> [--selftest]
"""
import json, sys
import numpy as np
from scipy.stats import wilcoxon

SCALE = np.array([.05, .10, .20])

def load_f(p):
    f = {}
    for l in open(p):
        r = json.loads(l)
        if r.get('no_valid'): f[(r['object'], r['event'])] = None
        else: f[(r['object'], r['event'])] = np.array([r['f_u'], r['f_I'], r['f_L']], float)
    return f

def per_object(rows, f, method, field='e'):
    acc = {}
    for r in rows:
        if r.get('method', 'G') != method or field not in r: continue
        key = (r['object'], r['event'])
        if f.get(key) is None: continue
        s = float(np.mean(np.maximum(np.array(r[field], float) - f[key], 0) / SCALE))
        acc.setdefault(key, []).append(s)
    ev = {}
    for (o, e), v in acc.items(): ev.setdefault(o, []).append(np.mean(v))
    return {o: float(np.mean(v)) for o, v in ev.items()}

def compare(SA, SB, a, b, alpha):
    objs = sorted(set(SA) & set(SB))
    sa = np.array([SA[o] for o in objs]); sb = np.array([SB[o] for o in objs])
    rel = (sa - sb) / sa
    p = float(wilcoxon(sa, sb, alternative='two-sided').pvalue) if np.any(sa != sb) else 1.0
    rng = np.random.default_rng(0)
    boot = [np.median(rng.choice(rel, len(rel))) for _ in range(5000)]
    lo, hi = np.percentile(boot, [5, 95])
    c = dict(A=a, B=b, n=len(objs), median_rel=float(np.median(rel)), p=p, alpha=alpha,
             B_wins=int(np.sum(sb < sa)), B_losses=int(np.sum(sb > sa)), ci90=[float(lo), float(hi)],
             median_S_A=float(np.median(sa)), median_S_B=float(np.median(sb)))
    if alpha is None: c['verdict'] = '描述性，不判'
    elif c['median_rel'] >= .20 and p < alpha and c['B_wins'] >= .75 * c['n']: c['verdict'] = f'{b} 优于 {a}'
    elif -c['median_rel'] >= .20 and p < alpha and c['B_losses'] >= .75 * c['n']: c['verdict'] = f'{a} 优于 {b}'
    elif abs(c['median_rel']) < .05 and lo > -.10 and hi < .10: c['verdict'] = '无差别'
    else: c['verdict'] = '不判'
    return c

def main():
    base = [json.loads(l) for l in open(sys.argv[1])]
    f = load_f(sys.argv[2])
    S = {m: per_object(base, f, m) for m in ('A0', 'A1', 'A2', 'A3', 'A4')}
    out = {'baseline_median_S': {m: float(np.median(list(v.values()))) for m, v in S.items()}}
    if '--selftest' in sys.argv:  # must reproduce L30.1f Q1: A2 0.97, A3 1.28, GCA vs A3 -23.2%, 20/24
        out['selftest_A2_vs_A3'] = compare(S['A3'], S['A2'], 'A3', 'A2', .01)
        print(json.dumps(out, indent=1, ensure_ascii=False)); return
    G = [dict(r, method='G') for r in map(json.loads, open(sys.argv[3]))]
    keys = {(r['object'], r['event'], r['seed']) for r in G if r.get('official_valid', True)}
    out['G_rows_valid'] = len(keys); out['G_complete'] = len(keys) == 24 * 12 * 3
    SG = per_object(G, f, 'G')
    out['G_median_S'] = float(np.median(list(SG.values())))
    if not out['G_complete'] or len(SG) != 24:
        out['main'] = '不完整，不判'
    else:
        out['main'] = compare(S['A2'], SG, 'A2', 'G', .01)
    out['descriptive'] = [compare(S[m], SG, m, 'G', None) for m in ('A3', 'A4')]
    if all('last_e' in r for r in G):
        out['G_last_round_median_S'] = float(np.median(list(per_object(G, f, 'G', 'last_e').values())))
        out['A2_last_round_median_S'] = float(np.median(list(per_object(base, f, 'A2', 'last_e').values())))
    out['per_object'] = {str(o): {'G': SG.get(o), 'A2': S['A2'].get(o), 'A3': S['A3'].get(o)} for o in sorted(S['A2'])}
    print(json.dumps(out, indent=1, ensure_ascii=False))

if __name__ == '__main__': main()
