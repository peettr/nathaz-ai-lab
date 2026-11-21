"""L22.10 M3 Q5 截断判据（方案 v2 §3.1，跑前写定）：对基底剪力 V(t) 做理想低通（截断频率 f_c=k·n1），
算单自由度（静力归一，H(f)=1/(1−r²+2iζr)，r=f/n1）峰值响应；ε=1−X̂_截断/X̂。ε<2% 可截断，2–5% 边缘，≥5% 不可截断。
  X̂ 取记录内沿均值方向的最大值（单样本）；另报 σ 的相对误差 ε_σ=1−σ_截断/σ。
  参照 X̂ 本身只含到数据带宽 f_lim（增益≤10）的荷载：带宽以上视为零，所以 ε 只计 k·n1 到 f_lim 之间的贡献（偏小，报告标明）；k·n1>f_lim 的格记 NaN。
  TPU 平滑件：频域乘 1/|H_d|（幅值反卷积，同 M2b 增益≤10），f>f_lim 置零。
网格：f1*=n1·H/U ∈ {0.10,0.15,0.20,0.30,0.40,0.50,0.60}；ζ ∈ {0.01,0.02,0.05,0.072}；k ∈ {1.2,1.5,2,3}。
V(t) 的几何与积分沿用 m2b_baseshear_q6.py 的 geometry()（同一来源，exec 其函数定义段）。
用法：python m3_q5_truncation.py <m2b脚本> <tpu_subset根> <坐标csv> <输出目录>
"""
import sys, os, glob, json, math
import numpy as np
from scipy.io import loadmat
m2b, root, coordf, out = sys.argv[1:5]; os.makedirs(out, exist_ok=True)
src = open(m2b).read().split("res = {'fstar_grid'")[0]
g = {'__name__': 'm2b_defs'}; sys.argv = ['x', root, coordf, out]; exec(compile(src, m2b, 'exec'), g)
geometry, C = g['geometry'], g['C']
F1 = [0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60]; ZG = [0.01, 0.02, 0.05, 0.072]; KG = [1.2, 1.5, 2.0, 3.0]
res = {'f1star': F1, 'zeta': ZG, 'k': KG, 'cases': {}}
for f in sorted(glob.glob(os.path.join(root, '*', '*', '*.mat'))):
    lib, case = f.split(os.sep)[-3], f.split(os.sep)[-2]
    taps, H0, Aw = geometry(C[(lib, case)])
    m = loadmat(f); cp = np.asarray(m['Wind_pressure_coefficients'], float); fs = float(np.squeeze(m['Sample_frequency']))
    H = float(np.squeeze(m['Building_height'])); tapno = np.asarray(m['Location_of_measured_points'])[2].astype(int)
    col = {int(t): j for j, t in enumerate(tapno)}; idx = np.array([col[t[0]] for t in taps])
    W = np.array([[t[1], t[2]] for t in taps]); Vx, Vy = (cp[:, idx] @ W).T
    V = Vx if abs(Vx.mean()) >= abs(Vy.mean()) else Vy
    U_H = 22.0 * (H / 10.0) ** 0.20 if lib == 'noeaves' else 23.4 * (H / 10.0) ** 0.20; N = 3 if lib == 'noeaves' else 5
    n = len(V); fr = np.fft.rfftfreq(n, 1 / fs); X = np.fft.rfft(V)
    Hd = np.ones_like(fr); nz = fr > 0; Hd[nz] = np.sin(np.pi * fr[nz] * N / fs) / (N * np.sin(np.pi * fr[nz] / fs))
    ok = (fr < fs / N) & (1 / np.maximum(Hd ** 2, 1e-12) <= 10); flim = float(fr[ok].max())
    Xc = np.where(fr <= flim, X / np.where(np.abs(Hd) > 1e-6, Hd, 1), 0)
    sgn = np.sign(V.mean()); tab = {}
    for f1s in F1:
        n1 = f1s * U_H / H
        for z in ZG:
            Hs = 1 / (1 - (fr / n1) ** 2 + 2j * z * fr / n1)
            x = np.fft.irfft(Xc * Hs, n); Xp = float((sgn * x).max()); sx = float(x.std())
            for k in KG:
                key = f'{f1s}_{z}_{k}'
                if k * n1 > flim: tab[key] = None; continue
                xt = np.fft.irfft(np.where(fr <= k * n1, Xc, 0) * Hs, n)
                tab[key] = dict(eps=round(1 - float((sgn * xt).max()) / Xp, 5), eps_sigma=round(1 - float(xt.std()) / sx, 5))
    res['cases'][os.path.relpath(f, root)] = dict(lib=lib, H=H, flim_fstar=flim * H / U_H, n=n, tab=tab)
    print('done', len(res['cases']), flush=True)
json.dump(res, open(os.path.join(out, 'm3_q5_tpu.json'), 'w'))
print('done', len(res['cases']))
