"""L22.10 网站图文报告配图（11-18）。只读已存结果 json，秒级；输出 PNG 与 numbers.json（正文数字由此程序生成）。
用法：python report_figs_20261118.py <m2_out 目录> <报告 figs 目录> <numbers.json 输出路径>
图：
 fig1 两层住宅实测 (n1,ζ) 成对值代入 TPU 主轴基底剪力：各对 A 最大值 vs U（层数匹配 H≥6 m），g_R=3.5 与 Davenport 并列；
 fig2 A 中位随约化频率 f* 的变化（TPU 主轴基底剪力，ζ=2.6/7.2/17.3%），标出住宅频带；
 fig3 1 Hz 基频按刚性略去共振的低估比例 s=A/(1+A) vs U（ζ=1/2/5%）；
 fig4 截断误差 ε 最大值 vs 截断倍数 k（TPU 整体、PRJ-5592 半屋面与屋面局部）；
 fig5 风速谱法/测压谱之比 r 的分布（两口径）。
"""
import sys, os, json, math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
from matplotlib import font_manager
for _f in ['./Windows/Fonts/NotoSansSC-VF.ttf', './Windows/Fonts/msyh.ttc']:
    if os.path.exists(_f): font_manager.fontManager.addfont(_f)
plt.rcParams['font.sans-serif'] = ['Noto Sans SC', 'Microsoft YaHei', 'Noto Sans CJK SC', 'Noto Sans CJK JP', 'WenQuanYi Zen Hei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
src, figd, numf = sys.argv[1:4]; os.makedirs(figd, exist_ok=True)
C1, C2, C3, INK, MUTED, GRID = '#2a78d6', '#eb6834', '#1baf7a', '#1f1f1e', '#6b6a65', '#e4e3df'
def style(ax):
    for s in ['top', 'right']: ax.spines[s].set_visible(False)
    for s in ['left', 'bottom']: ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED); ax.grid(axis='y', color=GRID, lw=0.8); ax.set_axisbelow(True)
def save(fig, n):
    p = os.path.join(figd, n); fig.savefig(p, dpi=150, bbox_inches='tight'); plt.close(fig); return p
NUM = {}
B = json.load(open(os.path.join(src, 'm2b_tpu.json'))); FG = np.array(B['fstar_grid']); CS = B['cases']
def gR_dav(n1, T=600.0):
    x = math.sqrt(2 * math.log(n1 * T)); return x + 0.5772 / x
def A_of(c, n1, z, U, gR=3.5, lin=False):
    v = c['V']; ph = np.array([np.nan if p is None else p for p in v['phiF']], float); fs_ = n1 * c['H'] / U
    if fs_ < FG[0] or fs_ > v['flim_fstar']: return None
    if lin: p = np.interp(fs_, FG, ph)
    else:
        ok = np.isfinite(ph) & (ph > 0); p = math.exp(np.interp(math.log(fs_), np.log(FG[ok]), np.log(ph[ok])))
    if not np.isfinite(p): return None
    xm, sB = abs(v['mean']), v['std']
    return (xm + math.sqrt((3.5*sB)**2 + gR**2*math.pi/(4*z)*p*sB**2)) / (xm + 3.5*sB) - 1
PAIRS = [(3.7, .039), (4.7, .036), (5.3, .032), (4.2, .040), (3.9, .031), (3.3, .036), (3.0, .047), (3.3, .034), (4.4, .022), (4.2, .039), (3.8, .031), (3.8, .048),
         (5.00, .019), (8.33, .013), (6.67, .073), (8.33, .040), (5.88, .034), (9.6, .051), (7.3, .035)]   # Matsunami 12 对、Hafeez 5 对、Hirashima 2 对
# ---- fig1
fig, ax = plt.subplots(figsize=(6.4, 4.0)); res1 = {}
for j, (gname, col, dx) in enumerate([('g_R=3.5', C1, -1.2), ('g_R Davenport', C2, 1.2)]):
    for U in (25, 35, 45):
        mx = []
        for n1, z in PAIRS:
            g = 3.5 if j == 0 else gR_dav(n1)
            a = [x for x in (A_of(c, n1, z, U, g) for c in CS.values() if c['H'] >= 6) if x is not None]
            if a: mx.append(max(a))
        mx = np.array(mx) * 100
        ax.scatter(np.full(len(mx), U + dx), mx, s=28, color=col, alpha=0.75, edgecolor='white', linewidth=0.6, label=gname if U == 25 else None, zorder=3)
        res1[f'{gname}|U{U}'] = dict(n_pairs=len(mx), max=round(float(mx.max()), 2), median_of_pair_max=round(float(np.median(mx)), 2), n_ge5=int((mx >= 5).sum()))
for y, t in [(2, '可忽略/边缘 2%'), (5, '边缘/可观 5%')]:
    ax.axhline(y, color=MUTED, lw=1, ls='--'); ax.text(28.5, y + 0.25, t, va='bottom', fontsize=8, color=MUTED)
ax.set_xticks([25, 35, 45]); ax.set_xlabel('屋面高平均风速 U（m/s）'); ax.set_ylabel('共振增量 A 的最大值（%）')
ax.set_title('两层住宅实测基频—阻尼对：主轴基底剪力共振增量', fontsize=10, color=INK); ax.legend(frameon=False, fontsize=8, loc='upper left'); style(ax)
save(fig, 'fig1_A_vs_U.png'); NUM['fig1'] = res1
# ---- fig2
fig, ax = plt.subplots(figsize=(6.4, 4.0)); res2 = {}
for z, col in [('0.026', C2), ('0.072', C1), ('0.173', C3)]:
    M = np.array([[np.nan if a is None else a for a in c['V']['A']['meas'][z]] for c in CS.values()], float)
    with np.errstate(all='ignore'): med = np.nanmedian(M, 0) * 100; n = np.isfinite(M).sum(0)
    ok = n >= 20; ax.plot(FG[ok], med[ok], color=col, lw=2, label=f'ζ={float(z)*100:.1f}%')
    res2[z] = {f'{f:.2f}': round(float(m), 2) for f, m, o in zip(FG, med, ok) if o and abs(f*50 - round(f*50)) < 1e-6 and round(f*50) % 10 == 0}
ax.axvspan(0.56, 1.72, color=GRID, alpha=0.6, lw=0); ax.text(0.6, ax.get_ylim()[1]*0.9 if ax.get_ylim()[1] > 0 else 1, '住宅基频与设计风速对应频带', fontsize=8, color=MUTED)
ax.axhline(5, color=MUTED, lw=1, ls='--'); ax.axhline(2, color=MUTED, lw=1, ls=':')
ax.set_yscale('log'); ax.set_xlabel('约化频率 f* = n1·H/U'); ax.set_ylabel('共振增量 A 中位（%，对数轴）')
ax.set_title('TPU 低层建筑主轴基底剪力：A 随约化频率下降', fontsize=10, color=INK); ax.legend(frameon=False, fontsize=8); style(ax)
save(fig, 'fig2_A_vs_fstar.png'); NUM['fig2'] = res2
# ---- fig3
fig, ax = plt.subplots(figsize=(6.4, 4.0)); res3 = {}
for z, col in [(0.01, C2), (0.02, C1), (0.05, C3)]:
    meds, mxs = [], []
    for U in (20, 30, 40):
        S = np.array([x for x in (A_of(c, 1.0, z, U, lin=True) for c in CS.values()) if x is not None]); s = S / (1 + S) * 100
        meds.append(np.median(s)); mxs.append(s.max())
    ax.plot([20, 30, 40], meds, color=col, lw=2, marker='o', ms=6, label=f'ζ={z*100:.0f}%（中位）')
    ax.plot([20, 30, 40], mxs, color=col, lw=1, ls='--', alpha=0.7)
    res3[f'{z}'] = dict(median=[round(float(m), 1) for m in meds], max=[round(float(m), 1) for m in mxs])
ax.axhline(5, color=MUTED, lw=1, ls='--')
ax.set_xticks([20, 30, 40]); ax.set_xlabel('屋面高平均风速 U（m/s）'); ax.set_ylabel('低估比例 s = A/(1+A)（%）')
ax.set_title('基频 1 Hz 按刚性略去共振：峰值基底剪力被低估（实线中位，虚线最大）', fontsize=9.5, color=INK); ax.legend(frameon=False, fontsize=8); style(ax)
save(fig, 'fig3_1Hz_underestimate.png'); NUM['fig3'] = res3
# ---- fig4
Q5 = json.load(open(os.path.join(src, 'm3_q5_tpu.json'))); Q5L = json.load(open(os.path.join(src, 'm3_q5_local_prj.json')))
fig, ax = plt.subplots(figsize=(6.4, 4.0)); res4 = {}
ks = Q5['k']
tpu = [max(c['tab'][key]['eps'] for c in Q5['cases'].values() for key in c['tab'] if key.endswith(f'_{k}') and c['tab'][key]) * 100 for k in ks]
def prj(w):
    out = []
    for k in ks:
        v = [s['max'] for case in Q5L['cases'].values() for key, s in case.items() if key.startswith(w + '|') and key.endswith(f'_{k}')]
        out.append(max(v) * 100 if v else np.nan)
    return out
series = [('TPU 主轴基底剪力', tpu, C1), ('PRJ-5592 半屋面', prj('whole'), C3), ('PRJ-5592 屋面 2 m 方窗', prj('2.0'), C2)]
for name, y, col in series:
    ax.plot(ks, y, color=col, lw=2, marker='o', ms=6, label=name); res4[name] = [round(float(v), 2) for v in y]
ax.axhline(2, color=MUTED, lw=1, ls='--'); ax.text(2.35, 2.15, '可截断界 2%', fontsize=8, color=MUTED, va='bottom')
ax.axhline(5, color=MUTED, lw=1, ls=':'); ax.text(2.35, 5.15, '5%', fontsize=8, color=MUTED, va='bottom')
ax.set_xticks(ks); ax.set_xlabel('截断频率 f_c = k·n1 中的 k'); ax.set_ylabel('峰值误差 ε 最大值（%）')
ax.set_title('荷载截断到 k 倍基频后的单自由度峰值误差', fontsize=10, color=INK); ax.legend(frameon=False, fontsize=8); style(ax)
save(fig, 'fig4_truncation.png'); NUM['fig4'] = res4
# ---- fig5
w = (FG >= 0.56) & (FG <= 1.72); r10, r3 = [], []
for c in CS.values():
    lib = c['lib']; H = c['H']; U = 22.0*(H/10)**0.2 if lib == 'noeaves' else 23.4*(H/10)**0.2
    fs = 15.0 if lib == 'noeaves' else 23.4375; N = 3 if lib == 'noeaves' else 5
    f = FG*U/H; Hd2 = (np.sin(np.pi*f*N/fs)/(N*np.sin(np.pi*f/fs)))**2
    r = np.array([np.nan if a is None else a for a in c['V']['r']['ka_chi']], float)
    r10 += list(r[w & np.isfinite(r)]); r3 += list(r[w & np.isfinite(r) & (1/Hd2 <= 3)])
r10, r3 = np.array(r10), np.array(r3)
fig, ax = plt.subplots(figsize=(6.4, 4.0)); bins = np.logspace(-1.5, 1, 40)
ax.hist(r10, bins=bins, color=C1, alpha=0.55, label=f'主口径（增益≤10，{len(r10)} 格）')
ax.hist(r3, bins=bins, color=C2, alpha=0.55, label=f'低增益口径（增益≤3，{len(r3)} 格）')
ax.axvspan(0.5, 2, color=GRID, alpha=0.5, lw=0); ax.axvline(1, color=MUTED, lw=1)
ax.set_xscale('log'); ax.set_xlabel('r = 风速谱法荷载谱 / 测压积分荷载谱（Kaimal×Vickery）'); ax.set_ylabel('格数')
ax.set_title('住宅频带内风速谱法多数偏低（灰带为 0.5–2 适用区）', fontsize=10, color=INK); ax.legend(frameon=False, fontsize=8); style(ax)
save(fig, 'fig5_q6_ratio.png')
NUM['fig5'] = {'main': dict(n=len(r10), median=round(float(np.median(r10)), 2), in_05_2=round(100*float(np.mean((r10 >= .5) & (r10 <= 2))), 1)),
               'lowgain': dict(n=len(r3), median=round(float(np.median(r3)), 2), in_05_2=round(100*float(np.mean((r3 >= .5) & (r3 <= 2))), 1))}
json.dump(NUM, open(numf, 'w'), ensure_ascii=False, indent=1)
print(json.dumps(NUM, ensure_ascii=False, indent=1))
