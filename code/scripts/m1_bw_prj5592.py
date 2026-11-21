"""L22.10 M1-2 PRJ-5592（WOW 1:10，512 Hz，管路已修正）带宽核定。判据在跑前写定：
逐测点谱（Welch，nperseg=4096）取中位数；噪声底 = 模型频率 200–250 Hz 内中位谱值；
f_ok = 谱 >= 10×噪声底 的最高模型频率。另报所有测点平均（等权）的谱同判据。
输出模型频率 f_ok 与 f_ok·H_m/U_m（H_m、U_m 未核，只给模型频率；约化频率在报告里换算）。
同时输出各测点谱的 2–250 Hz 斜率供目检。
"""
import sys, os, glob, json
import numpy as np
from scipy.io import loadmat
from scipy.signal import welch
root, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
fs = 512.0; res = {}
for f in sorted(glob.glob(os.path.join(root, '*', '*.mat'))):
    p = np.asarray(loadmat(f)['pDataCorrected'], float)
    if p.shape[0] < p.shape[1]: p = p.T
    p = p - p.mean(0)
    fr, P = welch(p, fs=fs, nperseg=4096, axis=0)
    Pm = np.median(P, axis=1)
    _, Pa = welch(p.mean(1), fs=fs, nperseg=4096)
    r = {}
    for name, S in [('tap_median', Pm), ('all_mean', Pa)]:
        w = (fr >= 200) & (fr <= 250)
        floor = float(np.median(S[w]))
        ok = (S >= 10 * floor) & (fr > 0.5)
        r[name] = dict(f_ok_model_Hz=float(fr[ok].max()) if ok.any() else float('nan'), floor=floor)
    r['shape'] = list(p.shape)
    res[os.path.relpath(f, root)] = r
    np.save(os.path.join(out, os.path.basename(f).replace('.mat', '_spec.npy')), np.vstack([fr, Pm, Pa]))
json.dump(res, open(os.path.join(out, 'm1_bw_prj5592.json'), 'w'), indent=1)
print('done', len(res))
