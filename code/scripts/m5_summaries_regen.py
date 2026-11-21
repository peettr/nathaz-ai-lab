"""L22.10 汇总表重生成（审查 23c6542f 第 14 条）：把 11-13/11-14 会话内临时代码固化，从已存 json 重算各摘要 txt。
输入目录 = m1_results/m2_out（含 m2b_tpu.json、m3_q5_tpu.json、m3_q5_local_prj.json、m3_q3_admittance_prj.json）。
输出到 <输出目录>，文件名与原摘要相同，供 diff 核对：
  m3_q2_near1Hz.txt（Q2）、m3_q5_summary.txt（Q5 整体）、m3_q3_admittance.txt（TPU 谱形导纳）、
  m3_q3_q5local_summary.txt（Q5 局部 + Q3 PRJ）、m2b_q6_tail.txt（Q6 两口径与同档率、增益检验，对应 m2b_summary_raw.txt 第 199–216 行）。
用法：python m5_summaries_regen.py <m2_out目录> <输出目录>
"""
import sys, os, json, math, contextlib
import numpy as np
src, out = sys.argv[1:3]; os.makedirs(out, exist_ok=True)
J = lambda n: json.load(open(os.path.join(src, n)))
B = J('m2b_tpu.json'); FG = np.round(np.array(B['fstar_grid']), 3); CS = B['cases']

def to(name):
    return contextlib.redirect_stdout(open(os.path.join(out, name), 'w'))

# ---- Q2（原代码：线性插值 phiF；保持原口径以便 diff）
with to('m3_q2_near1Hz.txt'):
    print('Q2：n1 在 1 Hz 附近、按刚性略去共振时，峰值基底剪力 V 低估的比例 s=A/(1+A)（%）；A 由测压积分谱，g=3.5，单模态白噪；f*=n1·H/U，H=各 TPU 件足尺高')
    print('n1  ζ    U  | 件数  s中位  s最大   (A中位 A最大)')
    for n1 in (1.0, 1.5, 2.0):
        for z in (0.01, 0.02, 0.05):
            for U in (20, 30, 40):
                S = []
                for c in CS.values():
                    v = c['V']; ph = np.array([np.nan if p is None else p for p in v['phiF']], float); fs_ = n1 * c['H'] / U
                    if fs_ < FG[0] or fs_ > v['flim_fstar']: continue
                    p = np.interp(fs_, FG, ph); xm = abs(v['mean']); sB = v['std']
                    S.append((xm + math.sqrt((3.5*sB)**2 + 3.5**2*math.pi/(4*z)*p*sB**2)) / (xm + 3.5*sB) - 1)
                S = np.array(S); s = S / (1 + S)
                print('%.1f %4.0f%% %3d | %3d  %5.1f  %5.1f   (%5.1f %5.1f)' % (n1, 100*z, U, len(S), 100*np.median(s), 100*s.max(), 100*np.median(S), 100*S.max()))

# ---- Q5 整体
Q5 = J('m3_q5_tpu.json')
with to('m3_q5_summary.txt'):
    print('Q5 截断误差 ε=1−X̂截断/X̂（%），基底剪力 V，TPU；中位 [最大] (≥2% 件占比, ≥5% 件占比) 件数')
    for f1 in Q5['f1star']:
        for z in Q5['zeta']:
            row = []
            for k in Q5['k']:
                e = np.array([c['tab'][f'{f1}_{z}_{k}']['eps'] for c in Q5['cases'].values() if c['tab'].get(f'{f1}_{z}_{k}')])
                row.append('k=%.1f: %5.2f [%5.2f] (%3.0f%%,%3.0f%%) n%3d' % (k, 100*np.median(e), 100*e.max(), 100*np.mean(e >= .02), 100*np.mean(e >= .05), len(e)) if len(e) else 'k=%.1f: -' % k)
            print(f'f1*={f1} ζ={z}: ' + ' | '.join(row))

# ---- Q3 TPU 谱形导纳
with to('m3_q3_admittance.txt'):
    pts = [0.1, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4]; ix = [int(np.argmin(abs(FG - p))) for p in pts]
    print('Q3 有效导纳 χ²_eff(f*)=φ_F,测压/φ_u,Kaimal(点，准定常)（方差按实测 σ_B 标定，只比谱形）与 Vickery χ²_V 之比；基底剪力 V；TPU')
    for lib in ['noeaves', 'eaves']:
        L = [c for c in CS.values() if c['lib'] == lib]
        r1 = np.array([[np.nan if a is None else a for a in c['V']['r']['ka_1']] for c in L], float)[:, ix]
        rc = np.array([[np.nan if a is None else a for a in c['V']['r']['ka_chi']] for c in L], float)[:, ix]
        eff = 1 / r1; vk = rc / r1
        with np.errstate(all='ignore'):
            print(f'== {lib} n={len(L)} f*=', pts)
            print('  χ²_eff 中位 ', ' '.join('%6.3f' % v for v in np.nanmedian(eff, 0)))
            print('  χ²_V   中位 ', ' '.join('%6.3f' % v for v in np.nanmedian(vk, 0)))
            print('  χ²_eff/χ²_V 中位', ' '.join('%6.2f' % v for v in np.nanmedian(eff / vk, 0)), '| 10–90 分位', ' '.join('%.2f–%.2f' % (np.nanpercentile(c, 10), np.nanpercentile(c, 90)) if np.isfinite(c).any() else '-' for c in (eff / vk).T))

# ---- Q5 局部 + Q3 PRJ
cfac = {'A20SH12': 18.72 / 21.51, 'A20SH00': 0.368 / 0.734}
Q5L = J('m3_q5_local_prj.json'); Q3 = J('m3_q3_admittance_prj.json')
with to('m3_q3_q5local_summary.txt'):
    print('Q5 局部（PRJ-5592）：ε 中位/最大（%）与 ≥2%、≥5% 窗占比，跨件取最坏；f1* 已按更正系数重标（实际 f1*=标注×c）')
    for grp, cc in cfac.items():
        L = [v for k, v in Q5L['cases'].items() if k.startswith(grp)]
        print(f'== {grp} 件数 {len(L)}')
        for w in ['whole', '2.0', '4.0', '8.0']:
            for k in Q5L['k']:
                rows = []
                for f1 in Q5L['f1star']:
                    for z in Q5L['zeta']:
                        key = f'{w}|{f1}_{z}_{k}'; S = [v[key] for v in L if key in v]
                        if S: rows.append((f1*cc, z, max(s['max'] for s in S), max(s['ge2'] for s in S), max(s['ge5'] for s in S), np.median([s['med'] for s in S])))
                if rows:
                    a = np.array(rows); print(f'  {w:5s} k={k}: 实际f1* {a[:,0].min():.2f}–{a[:,0].max():.2f}, ε中位≤{100*a[:,5].max():.2f}%, ε最大 {100*a[:,2].max():.2f}%, ≥2%窗占比最坏 {100*a[:,3].max():.0f}%, ≥5% {100*a[:,4].max():.0f}%  (格数{len(a)})')
                else: print(f'  {w:5s} k={k}: 全部超带宽')
    F3 = np.array(Q3['fstar_grid']); print('\nQ3 风速：', Q3['wind'])
    pts = [0.1, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2]; ix = [int(np.argmin(abs(F3 - p))) for p in pts]
    for grp in cfac:
        L = [v for k, v in Q3['cases'].items() if k.startswith(grp)]
        print(f'== {grp} n={len(L)}  f*=', pts)
        for w in ['whole', '2.0', '4.0', '8.0']:
            A = lambda key: np.array([[np.nan if x is None else x for x in v[w][key]] for v in L], float)[:, ix]
            with np.errstate(all='ignore'):
                m = np.nanmedian(A('chi2_med'), 0); V = np.nanmedian(A('chiV_med'), 0); r = np.nanmedian(A('ratio_med'), 0); lo = np.nanmin(A('ratio_med'), 0); hi = np.nanmax(A('ratio_med'), 0)
            f = lambda a: ' '.join('%6.3f' % x if np.isfinite(x) else '   -  ' for x in a)
            print(f'  {w:5s} 面积中位 {np.median([v[w]["area_med_m2"] for v in L]):.1f} m²')
            print('     χ²实测', f(m)); print('     χ²_V  ', f(V)); print('     比 中位', f(r), '| 件间 min', f(lo), 'max', f(hi))

# ---- Q6 尾段
with to('m2b_q6_tail.txt'):
    w = (FG >= 0.56) & (FG <= 1.72)
    tier = lambda a: np.where(np.isnan(a), np.nan, np.where(a < 0.02, 0, np.where(a < 0.05, 1, 2)))
    print('== Q6 汇总（f* 0.56–1.72 带宽内所有格；V 与 M）')
    for nm in ['V', 'M']:
        for meth in ['vk_chi', 'ka_chi']:
            r = np.array([[np.nan if a is None else a for a in c[nm]['r'][meth]] for c in CS.values()], float)[:, w].ravel(); r = r[np.isfinite(r)]
            outs = [f'{lo}-{hi}: {100*np.mean((r>=lo)&(r<=hi)):.1f}%' for lo, hi in [(0.5, 2), (0.67, 1.5), (0.33, 3)]]
            agree = []
            for z in ['0.026', '0.072', '0.173']:
                a = np.array([[np.nan if x is None else x for x in c[nm]['A']['meas'][z]] for c in CS.values()], float)[:, w]
                b = np.array([[np.nan if x is None else x for x in c[nm]['A'][meth][z]] for c in CS.values()], float)[:, w]
                m = np.isfinite(a) & np.isfinite(b); agree.append(f'z{z}:{100*np.mean(tier(a[m])==tier(b[m])):.1f}%')
            print(nm, meth, 'n', len(r), 'r<1 占 %.1f%%' % (100*np.mean(r < 1)), '| 落在', ' ; '.join(outs), '| 两法同档', ' '.join(agree))
    print('== 测压法 V：住宅 f* 0.56–1.72 内 A 最大值（逐案逐格）')
    for z in ['0.01', '0.026', '0.072', '0.173']:
        for lib in ['noeaves', 'eaves']:
            a = np.array([[np.nan if x is None else x for x in c['V']['A']['meas'][z]] for c in CS.values() if c['lib'] == lib], float)[:, w]
            i = np.unravel_index(np.nanargmax(a), a.shape); k = [k for k, c in CS.items() if c['lib'] == lib][i[0]]
            print(f'z={z} {lib}: max {100*np.nanmax(a):.2f}% at f*={FG[w][i[1]]} {k}; 超 5% 格占 {100*np.nanmean(a[np.isfinite(a)]>=0.05):.2f}% 超 2% 格占 {100*np.nanmean(a[np.isfinite(a)]>=0.02):.2f}%')
    print('== 反卷积噪声检验：只取增益 1/|H_d|^2 ≤ G 的格，f*≥0.56')
    for G in [10, 3, 1.5]:
        rr = []
        for c in CS.values():
            lib = c['lib']; H = c['H']; U = 22.0*(H/10)**0.2 if lib == 'noeaves' else 23.4*(H/10)**0.2
            fs = 15.0 if lib == 'noeaves' else 23.4375; N = 3 if lib == 'noeaves' else 5
            f = FG*U/H; Hd2 = (np.sin(np.pi*f*N/fs)/(N*np.sin(np.pi*f/fs)))**2; ok = (1/Hd2 <= G) & (FG >= 0.56)
            r = np.array([np.nan if a is None else a for a in c['V']['r']['ka_chi']], float)[ok]; rr += list(r[np.isfinite(r)])
        rr = np.array(rr)
        print(f'G≤{G} V ka_chi n={len(rr)} r中位 {np.median(rr):.2f} r<1 {100*np.mean(rr<1):.1f}% 0.5–2 {100*np.mean((rr>=.5)&(rr<=2)):.1f}%')
print('regen done', file=sys.stderr)

# ---- m2b_summary_raw.txt 前段（A 表、r、Shapley；11-13 原代码）
with to('m2b_summary_head.txt'):
    import collections
    cs = CS
    print('n', len(cs))
    print('along', collections.Counter((c['lib'], c['along']) for c in cs.values()))
    for nm in ['V', 'M']:
        for lib in ['noeaves', 'eaves']:
            L = [c for c in cs.values() if c['lib'] == lib]
            sm = np.array([c[nm]['std']/abs(c[nm]['mean']) for c in L]); fl = [c[nm]['flim_fstar'] for c in L]
            print(f'== {nm} {lib} n={len(L)} std/|mean| med {np.median(sm):.3f} [{sm.min():.3f},{sm.max():.3f}] flim {min(fl):.2f}-{max(fl):.2f}')
            pts = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6]; ix = [int(np.argmin(abs(FG-p))) for p in pts]
            for meth in ['meas', 'vk_chi', 'ka_chi', 'ka_1']:
                for z in ['0.01', '0.026', '0.072', '0.173']:
                    M = np.array([[np.nan if a is None else a for a in c[nm]['A'][meth][z]] for c in L], float)[:, ix]
                    with np.errstate(all='ignore'):
                        print(f'  {meth:7s} z={z:5s} med', ' '.join('%6.2f' % (100*v) if np.isfinite(v) else '   -  ' for v in np.nanmedian(M, 0)), '| max', ' '.join('%6.2f' % (100*v) if np.isfinite(v) else '   -  ' for v in np.nanmax(M, 0)))
            for meth in ['vk_chi', 'ka_chi', 'vk_1', 'ka_1']:
                M = np.array([[np.nan if a is None else a for a in c[nm]['r'][meth]] for c in L], float)[:, ix]
                with np.errstate(all='ignore'):
                    print(f'  r {meth:7s} med', ' '.join('%6.2f' % v if np.isfinite(v) else '   -  ' for v in np.nanmedian(M, 0)), '| min', ' '.join('%6.2f' % v if np.isfinite(v) else '   -  ' for v in np.nanmin(M, 0)), '| max', ' '.join('%6.2f' % v if np.isfinite(v) else '   -  ' for v in np.nanmax(M, 0)))
            print('  Shapley (V/M) median over cases: key A_base A_act share_f share_z share_spec n')
            keys = sorted({k for c in L for k in c[nm]['shapley']})
            for k in keys:
                S = [c[nm]['shapley'][k] for c in L if c[nm]['shapley'].get(k)]
                if not S: print('   ', k, 'all NaN'); continue
                g = lambda q: np.median([s[q] for s in S])
                print('   %-18s %.4f %.4f %.2f %.2f %.2f n=%d f*=%.2f' % (k, g('A_base'), g('A_act'), g('share_freq'), g('share_damp'), g('share_spec'), len(S), g('fstar_act')))

# ---- m2_A_summary_raw.txt（M2 屋面上拔 A，11-13 原代码）
with to('m2_A_summary_raw.txt'):
    pts = [0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6]
    for m in ['prj', 'tpu']:
        R = J(f'm2_A_{m}.json'); FS = np.round(np.array(R['fstar_grid']), 2)
        ix = [int(np.where(FS == p)[0][0]) for p in pts]
        groups = {}
        for k, c in R['cases'].items():
            g = k.split('/')[0] if m == 'prj' else c['lib']
            groups.setdefault(g, []).append(c)
        for g, L in groups.items():
            print(f'==== {m} {g} n={len(L)}  f*={pts}')
            for rt in ['1.0', '1.15']:
                for z in ['0.026', '0.072', '0.173']:
                    for ld in ['whole', 'half_a', 'half_b']:
                        M = np.array([[np.nan if a is None else a for a in c['res'][ld]['A'][rt][z]] for c in L], float)[:, ix]
                        n = np.sum(np.isfinite(M), 0)
                        with np.errstate(all='ignore'):
                            print(f'{rt} z={z} {ld:6s} med', ' '.join('%6.1f' % (100*v) if np.isfinite(v) else '   -  ' for v in np.nanmedian(M, 0)), '| max', ' '.join('%6.1f' % (100*v) if np.isfinite(v) else '   -  ' for v in np.nanmax(M, 0)), '| n', list(n))
                    for s in ['2.0', '4.0', '8.0']:
                        key = f'max_{rt}_{z}'
                        M = np.array([[np.nan if a is None else a for a in (c['res']['local'][s][key] or [None]*len(FS))] for c in L], float)[:, ix]
                        key2 = f'med_{rt}_{z}'
                        M2 = np.array([[np.nan if a is None else a for a in (c['res']['local'][s][key2] or [None]*len(FS))] for c in L], float)[:, ix]
                        with np.errstate(all='ignore'):
                            print(f'{rt} z={z} loc{s} winmed-med', ' '.join('%6.1f' % (100*v) if np.isfinite(v) else '   -  ' for v in np.nanmedian(M2, 0)), '| winmax-max', ' '.join('%6.1f' % (100*v) if np.isfinite(v) else '   -  ' for v in np.nanmax(M, 0)))
