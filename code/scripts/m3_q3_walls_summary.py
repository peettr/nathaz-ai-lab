"""汇总 m3_q3_walls_prj.json：每面/窗的 χ²、χ²_V、比（件中位的中位，件间 min/max），SH12 与 SH00 分列；迎风面选择计数。"""
import json, sys, collections
import numpy as np
Q = json.load(open(sys.argv[1])); FG = np.array(Q['fstar_grid'])
pts = [0.1, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2]; ix = [int(np.argmin(abs(FG - p))) for p in pts]
print('Q3 墙面/楼板底/屋角 实测导纳 χ²=S_F·U²/(4F̄²S_u)，比=χ²/χ²_V；件中位；f*=', pts, '；测点数', Q['n_taps'], Q['n_corner_taps'])
for grp in ['A20SH12', 'A20SH00']:
    L = [v for k, v in Q['cases'].items() if k.startswith(grp)]
    print(f'== {grp} n={len(L)} 迎风面选择:', dict(collections.Counter(v['windward_face'] for v in L)))
    keys = sorted({k for v in L for k in v if '|' in k})
    for key in keys:
        Lk = [v[key] for v in L if key in v]
        A = lambda q: np.array([[np.nan if x is None else x for x in d[q]] for d in Lk], float)[:, ix]
        with np.errstate(all='ignore'):
            m = np.nanmedian(A('chi2_med'), 0); V = np.nanmedian(A('chiV_med'), 0); r = np.nanmedian(A('ratio_med'), 0); lo = np.nanmin(A('ratio_med'), 0); hi = np.nanmax(A('ratio_med'), 0)
        f = lambda a: ' '.join('%6.3f' % x if np.isfinite(x) else '   -  ' for x in a)
        print(f'  {key:22s} 面积中位 {np.median([d["area_med_m2"] for d in Lk]):5.1f} m² 均值中位 {np.median([d["mean_med"] for d in Lk]):+.4f}')
        print('     χ²  ', f(m)); print('     χ²_V', f(V)); print('     比  ', f(r), '| 件间 min', f(lo), 'max', f(hi))
