"""L26.20: pooled B and C over storms, per EXPERIMENT_CARD_D1_Michael.md §6 (written 11-15 13:20, before Michael results).
usage: python combine_B_C.py <outjson> <B_json_1> <table_csv_1> <arm_1> [<B_json_2> <table_csv_2> <arm_2> ...]"""
import sys, json, csv, statistics as st, math
out = sys.argv[1]; a = sys.argv[2:]
Bmax = {q: [] for q in ['r_ew_rel', 'f_core', 'f_band', 'ph_ring', 'ph_band']}; diffs = []; per = {}
def fin(x): return x is not None and not (isinstance(x, float) and math.isnan(x))
for k in range(0, len(a), 3):
    bj, tc, arm = a[k:k + 3]; B = json.load(open(bj)); tm = {r['time'] for r in B}
    for r in B:
        for q in Bmax:
            v = r['max_' + q]
            if fin(v): Bmax[q].append(v)
    d = [float(r['fss_diff']) for r in csv.DictReader(open(tc)) if r['arm'] == arm and r['reff'] == 'main' and r['time'] in tm and r.get('fss_diff')]
    diffs += d; per[bj + ':' + arm] = dict(n=len(d), frac=sum(x > 0 for x in d) / len(d) if d else None, med=st.median(d) if d else None)
Bs = {q: (st.median(v) if v else None) for q, v in Bmax.items()}
Bs['n'] = len(Bmax['r_ew_rel']) if Bmax['r_ew_rel'] else 0
Bs['pass'] = bool(Bs['r_ew_rel'] is not None and Bs['r_ew_rel'] <= 0.15 and Bs['f_core'] <= 0.10 and Bs['f_band'] <= 0.10 and all(Bs[q] is None or Bs[q] <= 45 for q in ['ph_ring', 'ph_band']))
Cs = dict(n=len(diffs), frac_better=sum(x > 0 for x in diffs) / len(diffs), median_diff=st.median(diffs))
Cs['pass'] = bool(Cs['frac_better'] >= 2 / 3 and Cs['median_diff'] >= 0.05)
res = dict(B_pooled=Bs, C_pooled=Cs, C_per_storm=per)
json.dump(res, open(out, 'w'), indent=1); print(json.dumps(res, indent=1))
