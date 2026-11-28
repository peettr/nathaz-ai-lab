"""L22.10 M5 修订（审查 23c6542f）：小振幅实测成对 (n1, ζ) 全量代入 TPU 基底剪力（m2b_tpu.json），程序化出表。
成对值来源：Matsunami 2002 Table 2（PDF p.8，8 栋两层木住宅×桁行/梁间 16 对；IR 为全倒损伤房、SB 为改建中，单列标注）；
Hafeez 2019 Table 2（作者稿 PDF p.16–17：B30 横/纵、B36、B38、B39；周期换算）；Hirashima 1986（合订 PDF p.478–479：S-6、S-14）。
另列非成对的「组合假设」行（Matsunami 频率范围下端 3 Hz + 2%），只作敏感性。
A 定义同 m2b（g=3.5，单模态白噪，log 插值，f*>f_lim 不计）。H 两种口径：全部 TPU 件；层数匹配（两层住宅取 H≥6 m 的件）。
输出：每对 × U∈{25,35,45} × 口径 的 带宽内件数、A 中位、A 最大。
"""
import json, math, sys
import numpy as np
R = json.load(open(sys.argv[1])); FG = np.array(R['fstar_grid']); cs = R['cases']
P = [('Matsunami IS 桁', 3.7, .039, ''), ('Matsunami IS 梁', 4.7, .036, ''), ('Matsunami NK 桁', 5.3, .032, ''), ('Matsunami NK 梁', 4.2, .040, ''),
     ('Matsunami IK 桁', 3.9, .031, ''), ('Matsunami IK 梁', 3.3, .036, ''), ('Matsunami NH 桁', 3.0, .047, ''), ('Matsunami NH 梁', 3.3, .034, ''),
     ('Matsunami SK 桁', 4.4, .022, ''), ('Matsunami SK 梁', 4.2, .039, ''), ('Matsunami NM 桁', 3.8, .031, ''), ('Matsunami NM 梁', 3.8, .048, ''),
     ('Matsunami SB 桁', 4.3, .033, '改建中'), ('Matsunami SB 梁', 4.0, .030, '改建中'), ('Matsunami IR 桁', 2.5, .081, '全倒损伤'), ('Matsunami IR 梁', 2.7, .031, '全倒损伤'),
     ('Hafeez B30 横', 5.00, .019, ''), ('Hafeez B30 纵', 8.33, .013, ''), ('Hafeez B36', 6.67, .073, ''), ('Hafeez B38', 8.33, .040, ''), ('Hafeez B39', 5.88, .034, ''),
     ('Hirashima86 S-6', 9.6, .051, ''), ('Hirashima86 S-14', 7.3, .035, ''), ('组合假设 3 Hz+2%（非成对）', 3.0, .020, '非成对')]
def A_of(c, n1, z, U):
    v = c['V']; ph = np.array([np.nan if p is None else p for p in v['phiF']], float); fs_ = n1 * c['H'] / U
    if fs_ < FG[0] or fs_ > v['flim_fstar']: return None
    ok = np.isfinite(ph) & (ph > 0); p = math.exp(np.interp(math.log(fs_), np.log(FG[ok]), np.log(ph[ok])))
    xm, sB = abs(v['mean']), v['std']
    return (xm + math.sqrt((3.5 * sB) ** 2 + 3.5 ** 2 * math.pi / (4 * z) * p * sB ** 2)) / (xm + 3.5 * sB) - 1
print('H 值分布:', sorted(set(c['H'] for c in cs.values())))
print('%-30s %5s %5s %-6s | %s' % ('来源', 'n1', 'ζ%', '注', 'U=25 / 35 / 45：[全部件] n,中位,最大 ‖ [H≥6 m] n,中位,最大'))
for name, n1, z, note in P:
    out = []
    for U in (25, 35, 45):
        s = []
        for sel in (lambda c: True, lambda c: c['H'] >= 6):
            a = [x for x in (A_of(c, n1, z, U) for c in cs.values() if sel(c)) if x is not None]
            s.append('%3d,%5.2f,%5.2f' % (len(a), 100 * np.median(a), 100 * max(a)) if a else '  0,  -  ,  -  ')
        out.append(' ‖ '.join(s))
    print('%-30s %5.2f %5.1f %-6s | %s' % (name, n1, 100 * z, note, '  //  '.join(out)))
