"""L22.10 M3 Q5 局部荷载截断（PRJ-5592 512 Hz 管路修正件，屋面方窗；方案 v2 §3.1 Q5 判据，跑前写定）。
荷载：屋面方窗（边长 2/4/8 m 足尺，以每个测点为中心、半开区间）面积加权平均压力 F(t)；whole=半屋面整体。
  测点、从属面积同 m2_resonance_A.py（prj 分支）。风机/电气尖峰 47.0、93.75、187.5、230 Hz（模型）±0.5 Hz 先在频域置零。
带宽 f_lim：同 M1-2 事后判据（5 Hz 滑动中位谱 ≥10×200–250 Hz 底），逐窗计算；参照 X̂ 只含 f≤f_lim 的荷载（ε 偏小）。
SDOF：H(f)=1/(1−r²+2iζr)，r=f/n1；n1 由 f1*=n1·H_m/U_m 定（H_m=0.734 m，U_m=18.72 m/s）。
ε=1−X̂_截断/X̂（沿均值方向的记录最大值），f_c=k·n1；k·n1>f_lim 不计。
网格：f1* ∈ {0.3,0.5,0.7,1.0}；ζ ∈ {0.01,0.02,0.05}；k ∈ {1.2,1.5,2,3}。
输出：每件、每窗尺寸、每格的 ε 中位、最大、≥2%/≥5% 窗占比。
用法：python m3_q5_local_prj.py <prj5592_subset根> <prj5592_taps_AR2.0.csv> <输出目录>
"""
import sys, os, glob, json, csv
import numpy as np
from scipy.io import loadmat
from scipy.signal import welch
from scipy.ndimage import median_filter
from scipy.spatial import cKDTree
root, tabf, out = sys.argv[1:4]; os.makedirs(out, exist_ok=True)
rows = [r for r in csv.DictReader(open(tabf)) if 'oof' in r['surface']]
col = np.array([int(r['col']) - 1 for r in rows]); IN = 0.254
xy = np.array([[float(r['y_in']) * IN, float(r['x_in']) * IN] for r in rows])
g = 0.02; gx = np.arange(g / 2, 30 * IN, g); G = np.stack(np.meshgrid(gx, gx), -1).reshape(-1, 2)
Ai = np.bincount(cKDTree(xy).query(G)[1], minlength=len(rows)) * g * g
Hm, Um, fs = 0.734, 18.72, 512.0
F1 = [0.3, 0.5, 0.7, 1.0]; ZG = [0.01, 0.02, 0.05]; KG = [1.2, 1.5, 2.0, 3.0]
wins = [('whole', np.arange(len(rows)))]
for s in [2.0, 4.0, 8.0]:
    seen = set()
    for c in xy:
        m = np.where((xy[:, 0] >= c[0] - s / 2) & (xy[:, 0] < c[0] + s / 2) & (xy[:, 1] >= c[1] - s / 2) & (xy[:, 1] < c[1] + s / 2))[0]
        if len(m) and tuple(m) not in seen: seen.add(tuple(m)); wins.append((str(s), m))
res = {'f1star': F1, 'zeta': ZG, 'k': KG, 'n_windows': {k: sum(1 for w in wins if w[0] == k) for k in ['whole', '2.0', '4.0', '8.0']}, 'cases': {}}
for f in sorted(glob.glob(os.path.join(root, '*', '*.mat'))):
    p = np.asarray(loadmat(f)['pDataCorrected'], float)
    if p.shape[0] < p.shape[1]: p = p.T
    P = p[:, col]; n = P.shape[0]; fr = np.fft.rfftfreq(n, 1 / fs)
    notch = np.zeros_like(fr, bool)
    for t in [47.0, 93.75, 187.5, 230.0]: notch |= np.abs(fr - t) <= 0.5
    acc = {}
    for name, idx in wins:
        F = P[:, idx] @ (Ai[idx] / Ai[idx].sum())
        fw, S = welch(F - F.mean(), fs=fs, nperseg=4096); Ss = median_filter(S, 41, mode='nearest')
        fl = np.median(Ss[(fw >= 200) & (fw <= 250)]); ok = (Ss >= 10 * fl) & (fw > 0.5)
        flim = float(fw[ok].max()) if ok.any() else 0.0
        X = np.fft.rfft(F); X[notch] = 0; X[fr > flim] = 0; sgn = np.sign(F.mean())
        for f1s in F1:
            n1 = f1s * Um / Hm
            for z in ZG:
                Hs = 1 / (1 - (fr / n1) ** 2 + 2j * z * fr / n1)
                Xp = (sgn * np.fft.irfft(X * Hs, n)).max()
                for k in KG:
                    if k * n1 > flim: continue
                    e = 1 - (sgn * np.fft.irfft(np.where(fr <= k * n1, X, 0) * Hs, n)).max() / Xp
                    acc.setdefault(f'{name}|{f1s}_{z}_{k}', []).append(float(e))
    summ = {}
    for key, L in acc.items():
        a = np.array(L); summ[key] = dict(n=len(a), med=round(float(np.median(a)), 5), max=round(float(a.max()), 5),
                                          ge2=round(float(np.mean(a >= .02)), 4), ge5=round(float(np.mean(a >= .05)), 4))
    res['cases'][os.path.relpath(f, root)] = summ
    print('done', len(res['cases']), flush=True)
json.dump(res, open(os.path.join(out, 'm3_q5_local_prj.json'), 'w'))
print('done', len(res['cases']))
