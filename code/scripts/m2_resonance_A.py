"""L22.10 M2：测压积分屋面荷载谱与共振增量 A（Q1 主路线；判据见 00_启动方案 v2 §3.1，开跑前写定）。
定义：F(t) = Σ Cp_i(t)·A_i / ΣA_i（A_i 为平面投影从属面积；单位与原文件一致，A 为比值、单位抵消）。
  X̄=|mean F|；σ_B²=var F（全带宽准静态）；σ_R²=(π/(4ζ))·[f1·S_F(f1)]（单模态白噪近似，S_F 单边）；
  X̂_B=X̄+g_B σ_B；X̂=X̄+√(g_B²σ_B²+g_R²σ_R²)；A=X̂/X̂_B−1。
  f1 用约化频率 f*=f1·H/U 表示（f·S(f) 对时间尺度不变，A 只依赖 f*）。
参数（假设，报告标明）：g_B=3.5；g_R/g_B∈{1.0,1.15}；ζ∈{0.026,0.05,0.072,0.10,0.173}（CUREE W-11 范围与均值）；f* 网格 0.20–2.50 步 0.05。
带宽：TPU 平滑件按离散滑动平均 |H_d|² 反卷积，只在增益≤10 内有效（无檐 N=3、有檐 N=5）；
  PRJ-5592 用 5 Hz 滑动中位去尖峰后谱≥10×(200–250 Hz 底) 的最高频率（M1-2 事后判据），每个荷载各自判。超出带宽的 A 记 NaN。
荷载：whole（所有屋面测点）；half_a/half_b（屋脊两侧，按横向坐标中线分）；local_s（边长 s=2/4/6/8 m 足尺方窗，以每个测点为中心、半开区间，取窗内测点面积加权；报各窗 A 的最大、中位）。
用法：python m2_resonance_A.py tpu <tpu_subset根> <m2_tributary_area.csv> <输出目录>
      python m2_resonance_A.py prj <prj5592_subset根> <prj5592_taps_AR2.0.csv> <输出目录>
"""
import sys, os, glob, json, csv, math
import numpy as np
from scipy.io import loadmat
from scipy.signal import welch
from scipy.ndimage import median_filter
from scipy.spatial import cKDTree
mode, root, tabf, out = sys.argv[1:5]; os.makedirs(out, exist_ok=True)
FS = np.round(np.arange(0.20, 2.5001, 0.05), 2); ZETA = [0.026, 0.05, 0.072, 0.10, 0.173]; GB = 3.5; RAT = [1.0, 1.15]
SIDES = [2.0, 4.0, 6.0, 8.0]

def Atab(F, fr, S, flim, Hs_over_U):
    """F 时程，fr/S 谱（已校正），flim 有效上限（Hz，同 fr 时间尺度），Hs_over_U = H/U（同尺度）。返回 A[ratio][zeta][f*] 列表。"""
    xm = abs(F.mean()); sB = F.std()
    fstar = fr * Hs_over_U
    fS = fr * S
    res = {}
    for rt in RAT:
        res[str(rt)] = {}
        for z in ZETA:
            row = []
            for fs_ in FS:
                f1 = fs_ / Hs_over_U
                if f1 > flim or f1 < fr[1]: row.append(None); continue
                v = np.interp(np.log(fs_), np.log(fstar[1:]), fS[1:])
                sR2 = math.pi / (4 * z) * v
                XB = xm + GB * sB; X = xm + math.sqrt((GB * sB) ** 2 + (rt * GB) ** 2 * sR2)
                row.append(round(X / XB - 1, 5))
            res[str(rt)][str(z)] = row
    return dict(mean=float(F.mean()), std=float(sB), flim_fstar=float(flim * Hs_over_U), A=res)

def spec(F, fs, nper):
    fr, S = welch(F - F.mean(), fs=fs, nperseg=nper); return fr, S

def windows(xy, A_i):
    """返回 [(side, idx数组)]，足尺坐标 xy。"""
    out_ = []
    for s in SIDES:
        seen = set()
        for c in xy:
            m = np.where((xy[:, 0] >= c[0] - s / 2) & (xy[:, 0] < c[0] + s / 2) & (xy[:, 1] >= c[1] - s / 2) & (xy[:, 1] < c[1] + s / 2))[0]
            key = tuple(m)
            if len(m) and key not in seen: seen.add(key); out_.append((s, m))
    return out_

def run_case(cp, xy, Ai, fs, nper, HU, flim_fn, ymid):
    res = {}
    def one(idx):
        w = Ai[idx] / Ai[idx].sum(); F = cp[:, idx] @ w
        fr, S, flim = flim_fn(F)
        return Atab(F, fr, S, flim, HU)
    allidx = np.arange(len(Ai))
    res['whole'] = one(allidx)
    res['half_a'] = one(allidx[xy[:, 1] < ymid]); res['half_b'] = one(allidx[xy[:, 1] >= ymid])
    loc = {}
    for s, idx in windows(xy, Ai):
        loc.setdefault(str(s), []).append(one(idx))
    summ = {}
    for s, L in loc.items():
        summ[s] = {'n_windows': len(L), 'area_mean_m2': None}
        for rt in map(str, RAT):
            for z in map(str, ZETA):
                M = np.array([[np.nan if a is None else a for a in r['A'][rt][z]] for r in L], float)
                with np.errstate(all='ignore'):
                    summ[s][f'max_{rt}_{z}'] = [None if np.isnan(v) else round(float(v), 5) for v in np.nanmax(M, 0)] if np.isfinite(M).any() else None
                    summ[s][f'med_{rt}_{z}'] = [None if np.isnan(v) else round(float(v), 5) for v in np.nanmedian(M, 0)] if np.isfinite(M).any() else None
        summ[s]['flim_fstar_min'] = float(min(r['flim_fstar'] for r in L))
    res['local'] = summ
    return res

R = {'fstar_grid': FS.tolist(), 'zeta': ZETA, 'gB': GB, 'gR_over_gB': RAT, 'cases': {}}
if mode == 'tpu':
    T = {}
    for r in csv.DictReader(open(tabf)): T.setdefault((r['lib'], r['case']), {})[int(r['tap'])] = (float(r['x_fs']), float(r['y_fs']), float(r['A_plan']))
    for f in sorted(glob.glob(os.path.join(root, '*', '*', '*.mat'))):
        lib, case = f.split(os.sep)[-3], f.split(os.sep)[-2]
        m = loadmat(f); cp = np.asarray(m['Wind_pressure_coefficients'], float)
        fs = float(np.squeeze(m['Sample_frequency'])); H = float(np.squeeze(m['Building_height']))
        loc = np.asarray(m['Location_of_measured_points']); tapno = loc[2].astype(int)
        tt = T[(lib, case)]; col = {int(t): j for j, t in enumerate(tapno)}
        miss = [t for t in tt if t not in col]
        if miss: raise SystemExit(f'tap mismatch {lib} {case} {miss[:5]}')
        taps = sorted(tt); idx = np.array([col[t] for t in taps])
        # 核：csv 坐标与 mat 坐标的一致性（只记录相关系数，不同单位）
        xy = np.array([tt[t][:2] for t in taps]); Ai = np.array([tt[t][2] for t in taps])
        cc = float(np.corrcoef(np.abs(loc[0][idx]), np.abs(xy[:, 0]))[0, 1]) if np.std(loc[0][idx]) > 0 else float('nan')
        cpr = cp[:, idx]
        U_H = 22.0 * (H / 10.0) ** 0.20 if lib == 'noeaves' else 23.4 * (H / 10.0) ** 0.20  # 同 M1-1 v3
        N = 3 if lib == 'noeaves' else 5
        def flim_fn(F, fs=fs, N=N):
            fr, S = spec(F, fs, 1024)
            Hd2 = np.ones_like(fr); nz = fr > 0
            Hd2[nz] = (np.sin(np.pi * fr[nz] * N / fs) / (N * np.sin(np.pi * fr[nz] / fs))) ** 2
            ok = (1 / np.maximum(Hd2, 1e-12)) <= 10
            flim = float(fr[ok & (fr < fs / N)].max())
            return fr, S / np.maximum(Hd2, 1e-12), flim
        R['cases'][os.path.relpath(f, root)] = dict(lib=lib, H=H, U_H_assumed=U_H, fs=fs, n_roof_taps=len(taps), xcorr_check=cc,
                                                   res=run_case(cpr, xy, Ai, fs, 1024, H / U_H, flim_fn, 0.0))
        print('done', len(R['cases']), flush=True)
else:
    rows = [r for r in csv.DictReader(open(tabf)) if 'oof' in r['surface']]
    col = np.array([int(r['col']) - 1 for r in rows]); IN = 0.0254 * 10  # 模型英寸→足尺米（1:10）
    xy_fs = np.array([[float(r['y_in']) * IN, float(r['x_in']) * IN] for r in rows])  # 列0沿长边(y_in)，列1横向(x_in)
    # 从属面积：平面 x_in∈[0,30]、y_in∈[0,30]（半屋面）内 Voronoi
    g = 0.02; box = (0, 30 * IN, 0, 30 * IN)
    gx = np.arange(box[0] + g / 2, box[1], g); gy = np.arange(box[2] + g / 2, box[3], g)
    G = np.stack(np.meshgrid(gx, gy), -1).reshape(-1, 2); nn = cKDTree(xy_fs).query(G)[1]
    Ai = np.bincount(nn, minlength=len(rows)) * g * g
    Hm, Um = 0.734, 18.72; fs = 512.0
    def flim_fn(F):
        fr, S = spec(F, fs, 4096); Ss = median_filter(S, 41, mode='nearest')
        fl = np.median(Ss[(fr >= 200) & (fr <= 250)]); ok = (Ss >= 10 * fl) & (fr > 0.5)
        return fr, S, float(fr[ok].max()) if ok.any() else 0.0
    for f in sorted(glob.glob(os.path.join(root, '*', '*.mat'))):
        p = np.asarray(loadmat(f)['pDataCorrected'], float)
        if p.shape[0] < p.shape[1]: p = p.T
        R['cases'][os.path.relpath(f, root)] = dict(n_roof_taps=len(rows), area_sum_m2=float(Ai.sum()),
                                                   res=run_case(p[:, col], xy_fs, Ai, fs, 4096, Hm / Um, flim_fn, 15 * IN))
        print('done', len(R['cases']), flush=True)
json.dump(R, open(os.path.join(out, f'm2_A_{mode}.json'), 'w'))
print('done', len(R['cases']))
