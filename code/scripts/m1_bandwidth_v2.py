"""L22.10 M1-1 测压带宽核定（判据在跑前写定，见 M1_带宽初核_20261112.md）。
对每个文件：逐测点 Cp 谱、屋面面积平均 Cp 谱（等权，从属面积表另做），
与足尺 0.2 s 矩形滑动平均的 |H|^2=sinc^2(fT) 比较；噪声底取第一零点(5 Hz)附近
±0.3 Hz 窗内谱中位数。可信上限 f_ok：反卷积后谱 S/|H|^2 仍 >= 10×噪声底/|H|^2 的最高频率
（即原始谱高于噪声底 10 倍）。输出 json：每文件 f_ok（足尺 Hz）与对应 nH/U。
用法：python m1_bandwidth.py <tpu_subset根> <输出目录>
"""
import sys, os, json, glob
import numpy as np
from scipy.io import loadmat
from scipy.signal import welch
root, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
res = {}
for f in sorted(glob.glob(os.path.join(root, '*', '*', '*.mat'))):
    m = loadmat(f)
    cp = np.asarray(m['Wind_pressure_coefficients'], float)
    fs = float(np.squeeze(m['Sample_frequency']))
    H = float(np.squeeze(m['Building_height']))
    loc = np.asarray(m['Location_of_measured_points'])
    face = loc[3].astype(int)
    lib = f.split(os.sep)[-3]
    roof = (face == 1) if lib == 'eaves' else (face >= 5)
    sig = {'tap_median': None, 'roof_mean': cp[:, roof].mean(1)}
    nper = 1024
    fr, P = welch(cp - cp.mean(0), fs=fs, nperseg=nper, axis=0)
    Ptap = np.median(P, axis=1)
    _, Proof = welch(sig['roof_mean'] - sig['roof_mean'].mean(), fs=fs, nperseg=nper)
    N = 3 if lib == 'noeaves' else 5; f0 = fs / N  # 离散滑动平均第一零点（v2 第1节）
    out_f = {}
    for name, S in [('tap_median', Ptap), ('roof_mean', Proof)]:
        w = (fr > f0 - 0.3) & (fr < f0 + 0.3)
        floor = np.median(S[w]) if w.any() else np.nan
        okm = S >= 10 * floor
        f_ok = float(fr[okm & (fr < f0)].max()) if (okm & (fr < f0)).any() else float('nan')
        out_f[name] = dict(f_ok_Hz=f_ok, floor=float(floor))
    U_H = 22.0 * (H / 10.0) ** 0.20 if lib == 'noeaves' else 23.4 * (H / 10.0) ** 0.20
    for k in out_f: out_f[k]['nH_U'] = out_f[k]['f_ok_Hz'] * H / U_H
    out_f.update(fs=fs, H=H, U_H_assumed=U_H, lib=lib)
    res[os.path.relpath(f, root)] = out_f
json.dump(res, open(os.path.join(out, 'm1_bandwidth_v2.json'), 'w'), indent=1)
print('done', len(res))
