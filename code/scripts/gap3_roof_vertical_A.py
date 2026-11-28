"""L22.10 缺口③（11-28，按增补判据：A 级 ≥3 条、≥2 篇 → 补 Q1 竖向分量估算，楼板实测作屋盖「替代对象」）。
替代参数（Lead 已核原文）：Suzuki 等 2012 轻木根太楼板 19.2 Hz/3.3%（PDF p.4）；Faircloth 等 2026 CLT TF1 8.83 Hz/3.24%、TF3 3.51 Hz/3.00%（Table 4，p.7）；
SCI P354 L2 轻钢楼板 14.0 Hz/6.6%（B 级，方法缺，只作并列）。
荷载：M2 屋面上拔面积平均荷载（TPU 整屋面 whole；PRJ-5592 SH12 半屋面 whole）。M2 只存了 ζ 网格上的 A，故由 ζ0=2.6% 的 A 反解：
  X̂=(1+A)X̂_B，σ_R²(ζ0)=((X̂−X̄)²−(3.5σ_B)²)/3.5²，σ_R²(ζ)=σ_R²(ζ0)·ζ0/ζ，再按 A 定义重算（g_B=g_R=3.5）。
f*=n1·H/U：TPU 用各件 H（M2 中 H 为足尺）；PRJ SH12 标注 f* 乘 0.8703 更正。U∈{25,35,45} m/s，带宽外不计。
"""
import json, math, sys
import numpy as np
src = sys.argv[1]
P = [('Suzuki2012 轻木楼板', 19.2, .033, 'A'), ('Faircloth2026 CLT TF1', 8.83, .0324, 'A'), ('Faircloth2026 CLT TF3', 3.51, .030, 'A'), ('SCI P354 L2 轻钢楼板', 14.0, .066, 'B')]
def run(cases, Hof, cfac):
    out = {}
    for name, n1, z, g in P:
        for U in (25, 35, 45):
            As = []
            for c in cases:
                w = c['res']['whole']; FS = np.array(c['_fs']) * cfac
                fs_ = n1 * Hof(c) / U
                if fs_ > w['flim_fstar'] * cfac or fs_ < FS[0]: continue
                a0 = np.array([np.nan if x is None else x for x in w['A']['1.0']['0.026']], float)
                if not np.isfinite(a0).any(): continue
                ok = np.isfinite(a0); A0 = np.interp(fs_, FS[ok], a0[ok])
                xm, sB = abs(w['mean']), w['std']; XB = xm + 3.5 * sB; X = (1 + A0) * XB
                sR2 = ((X - xm) ** 2 - (3.5 * sB) ** 2) / 3.5 ** 2 * 0.026 / z
                As.append((xm + math.sqrt((3.5 * sB) ** 2 + 3.5 ** 2 * sR2)) / XB - 1)
            out[(name, U)] = (len(As), 100 * np.median(As) if As else None, 100 * max(As) if As else None)
    return out
T = json.load(open(src + '/m2_A_tpu.json')); Pj = json.load(open(src + '/m2_A_prj.json'))
for d in (T, Pj):
    for c in d['cases'].values(): c['_fs'] = d['fstar_grid']
# TPU: M2 json 存 H（足尺 m）
tpu = run([c for c in T['cases'].values()], lambda c: c['H'], 1.0)
prj = run([c for k, c in Pj['cases'].items() if k.startswith('A20SH12')], lambda c: 0.734 * 10, 18.72 / 21.51)
print('屋面上拔（整屋面/半屋面）共振增量 A（%）：件数, 中位, 最大；带宽外不计。替代对象=楼板实测。')
for name, n1, z, g in P:
    for U in (25, 35, 45):
        a, b = tpu[(name, U)], prj[(name, U)]
        f = lambda t: '%3d, %s, %s' % (t[0], '-' if t[1] is None else '%.2f' % t[1], '-' if t[2] is None else '%.2f' % t[2])
        print(f'{name:22s} {n1:5.2f} Hz ζ={z*100:.2f}% [{g}] U={U}: TPU {f(a)} | PRJ SH12 {f(b)}')

# ---- 带宽外外推（假设，敏感性）：对每件，用带宽上半段（f* 从 0.5·f_lim 到 f_lim）的 σ_R²(ζ0)∝f·S(f) 拟合对数斜率，外推到目标 f*，再按 ζ 换算 A
def run_ex(cases, Hof, cfac):
    out = {}
    for name, n1, z, g in P:
        for U in (25, 35, 45):
            As, slopes = [], []
            for c in cases:
                w = c['res']['whole']; FS = np.array(c['_fs']) * cfac; fl = w['flim_fstar'] * cfac
                a0 = np.array([np.nan if x is None else x for x in w['A']['1.0']['0.026']], float)
                xm, sB = abs(w['mean']), w['std']; XB = xm + 3.5 * sB
                sR = ((((1 + a0) * XB - xm) ** 2 - (3.5 * sB) ** 2) / 3.5 ** 2)
                m = np.isfinite(sR) & (sR > 0) & (FS >= 0.5 * fl) & (FS <= fl)
                if m.sum() < 3: continue
                k, b0 = np.polyfit(np.log(FS[m]), np.log(sR[m]), 1); slopes.append(k)
                fs_ = n1 * Hof(c) / U
                s2 = math.exp(b0 + k * math.log(fs_)) * 0.026 / z
                As.append((xm + math.sqrt((3.5 * sB) ** 2 + 3.5 ** 2 * s2)) / XB - 1)
            out[(name, U)] = (len(As), 100 * np.median(As) if As else None, 100 * max(As) if As else None, np.median(slopes) if slopes else None)
    return out
te = run_ex([c for c in T['cases'].values()], lambda c: c['H'], 1.0)
pe = run_ex([c for k, c in Pj['cases'].items() if k.startswith('A20SH12')], lambda c: 0.734 * 10, 18.72 / 21.51)
print('\n带宽外幂律外推（假设：f·S(f) 在带宽上半段的对数斜率延续到目标 f*；斜率为件中位）')
for name, n1, z, g in P:
    for U in (25, 35, 45):
        a, b = te[(name, U)], pe[(name, U)]
        f = lambda t: '%3d, 中位 %.2f, 最大 %.2f, 斜率 %.2f' % t
        print(f'{name:22s} {n1:5.2f} Hz ζ={z*100:.2f}% U={U}: TPU {f(a)} | PRJ SH12 {f(b)}')
