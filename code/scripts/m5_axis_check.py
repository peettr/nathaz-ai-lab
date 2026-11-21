"""审查 23c6542f 必须改 1 的敏感性：只取风向 0°/90°（及有檐库对应正交向）的件，此时所选主轴分量即顺风向；与全部风向对比。成对值同 m5_small_amp_pairs_v2.py 中 NH 梁、SK 桁、B30 横。"""
import json, math, sys, re
import numpy as np
R = json.load(open(sys.argv[1])); FG = np.array(R['fstar_grid']); cs = R['cases']
def A_of(c, n1, z, U):
    v = c['V']; ph = np.array([np.nan if p is None else p for p in v['phiF']], float); fs_ = n1 * c['H'] / U
    if fs_ < FG[0] or fs_ > v['flim_fstar']: return None
    ok = np.isfinite(ph) & (ph > 0); p = math.exp(np.interp(math.log(fs_), np.log(FG[ok]), np.log(ph[ok])))
    xm, sB = abs(v['mean']), v['std']
    return (xm + math.sqrt((3.5*sB)**2 + 3.5**2*math.pi/(4*z)*p*sB**2)) / (xm + 3.5*sB) - 1
ang = lambda k: int(re.findall(r'/(\d+)\.mat', k)[0])
print('风向分布:', sorted(set(ang(k) for k in cs)))
for name, n1, z in [('NH 梁', 3.3, .034), ('SK 桁', 4.4, .022), ('B30 横', 5.0, .019)]:
    for U in (25, 35, 45):
        r = []
        for lab, sel in [('全部风向', lambda k: True), ('仅轴向风 0/90/180/270', lambda k: ang(k) % 90 == 0)]:
            a = [x for x in (A_of(c, n1, z, U) for k, c in cs.items() if sel(k)) if x is not None]
            r.append('%s n=%d 中位 %.2f 最大 %.2f' % (lab, len(a), 100*np.median(a), 100*max(a)) if a else lab + ' n=0')
        print(name, 'U=%d: ' % U + ' | '.join(r))
