"""L22.10 g_R 敏感性（根 Lead 11-14 委托）：在 m5_small_amp_pairs_v2.py 基础上，共振峰值因子改用 Davenport 式 g_R=√(2ln(n1·T))+0.5772/√(2ln(n1·T))，T=600 s（10 min 平均时距，足尺）；g_B 仍取 3.5。主表（g_R=3.5）不改，本表并列新旧。
原说明：小振幅实测成对 (n1, ζ) 全量代入 TPU 基底剪力（m2b_tpu.json），程序化出表。
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
def gR_dav(n1, T=600.0):
    x = math.sqrt(2 * math.log(n1 * T)); return x + 0.5772 / x
def A_of(c, n1, z, U, gR=3.5):
    v = c['V']; ph = np.array([np.nan if p is None else p for p in v['phiF']], float); fs_ = n1 * c['H'] / U
    if fs_ < FG[0] or fs_ > v['flim_fstar']: return None
    ok = np.isfinite(ph) & (ph > 0); p = math.exp(np.interp(math.log(fs_), np.log(FG[ok]), np.log(ph[ok])))
    xm, sB = abs(v['mean']), v['std']
    return (xm + math.sqrt((3.5 * sB) ** 2 + gR ** 2 * math.pi / (4 * z) * p * sB ** 2)) / (xm + 3.5 * sB) - 1
print('A=X̂/X̂_B−1；X̂_B=X̄+3.5σ_B；X̂=X̄+√((3.5σ_B)²+g_R²σ_R²)；σ_R²=(π/4ζ)f1S(f1)；g_R 旧=3.5，新=Davenport(n1,T=600 s)')
print('%-30s %5s %5s %5s | %s' % ('来源', 'n1', 'ζ%', 'g_R新', 'U=25 / 35 / 45：A 最大 旧→新 [全部件] ‖ [H≥6 m]'))
tot = {}
for name, n1, z, note in P:
    g = gR_dav(n1); out = []
    for U in (25, 35, 45):
        s = []
        for tag, sel in (('all', lambda c: True), ('h6', lambda c: c['H'] >= 6)):
            a0 = [x for x in (A_of(c, n1, z, U) for c in cs.values() if sel(c)) if x is not None]
            a1 = [x for x in (A_of(c, n1, z, U, g) for c in cs.values() if sel(c)) if x is not None]
            if a0:
                s.append('%5.2f→%5.2f' % (100 * max(a0), 100 * max(a1)))
                if note == '': tot.setdefault((U, tag), []).append((max(a0), max(a1), name))
            else: s.append('   -  →  -  ')
        out.append(' ‖ '.join(s))
    print('%-30s %5.2f %5.1f %5.2f %-6s | %s' % (name, n1, 100 * z, g, note, '  //  '.join(out)))
print('\n汇总（只计成对实测、正常住宅，不含 IR/SB/非成对行）：各 U、口径下各对最大值中的最大，旧→新；以及 ≥5% 的对数')
for (U, tag), L in sorted(tot.items()):
    o = max(L, key=lambda t: t[0]); n = max(L, key=lambda t: t[1])
    print('U=%d %-3s 最大 旧 %.2f%%（%s） 新 %.2f%%（%s）；≥5%% 的对数 旧 %d 新 %d；≥2%% 旧 %d 新 %d；对数 %d' % (U, tag, 100*o[0], o[2], 100*n[1], n[2], sum(t[0]>=.05 for t in L), sum(t[1]>=.05 for t in L), sum(t[0]>=.02 for t in L), sum(t[1]>=.02 for t in L), len(L)))
