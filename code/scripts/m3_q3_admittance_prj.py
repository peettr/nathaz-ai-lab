"""L22.10 M3 Q3 屋面荷载气动导纳实测（PRJ-5592，跑前写定）。
定义（准定常）：F(t)=Σp_i·A_i/ΣA_i（屋面方窗或半屋面），χ²(f)=S_F(f)·U²/(4·F̄²·S_u(f))；χ²=1 即准定常点荷载。
  S_u 取 WindSpeedData 中同架空高度、同风机档（040perc）的 Cobra 纵向风速 U(t)（A25 系列；压力为 A20 系列，**假设**同一来流）：
  SH12 压力 ↔ (Ve)E – A25SH12（U=21.51 m/s）；SH00 ↔ (Ve)B – A25SH00（U=18.72 m/s）。
  压力 512 Hz、风速 2500 Hz，各自 Welch（压力 nperseg 4096；风速 nperseg 20000），插值到同一 f* 网格；f*=f·H/U，H：SH12 0.734 m、SH00 0.368 m。
  压力谱先去 47.0/93.75/187.5/230 Hz ±0.5 Hz 尖峰（线性插补），带宽同 M1-2 事后判据，逐窗。
对照：Vickery χ²_V=1/[1+(2f√A/U)^{4/3}]²（A=窗面积），即相干理论折减的常用拟合。
差别：Δ(f*)=χ²_实测/χ²_V。
输出：每件、每窗尺寸（whole/2/4/8 m）的 χ²_实测 中位与 10/90 分位、χ²_V、在 f* 网格 0.05–2.0。
用法：python m3_q3_admittance_prj.py <prj5592_subset根> <taps csv> <wind目录> <输出目录>
"""
import sys, os, glob, json, csv
import numpy as np
from scipy.io import loadmat
from scipy.signal import welch
from scipy.ndimage import median_filter
from scipy.spatial import cKDTree
root, tabf, wdir, out = sys.argv[1:5]; os.makedirs(out, exist_ok=True)
rows = [r for r in csv.DictReader(open(tabf)) if 'oof' in r['surface']]
col = np.array([int(r['col']) - 1 for r in rows]); IN = 0.254
xy = np.array([[float(r['y_in']) * IN, float(r['x_in']) * IN] for r in rows])
g = 0.02; gx = np.arange(g / 2, 30 * IN, g); G = np.stack(np.meshgrid(gx, gx), -1).reshape(-1, 2)
Ai = np.bincount(cKDTree(xy).query(G)[1], minlength=len(rows)) * g * g     # 足尺 m²
wins = [('whole', np.arange(len(rows)))]
for s in [2.0, 4.0, 8.0]:
    seen = set()
    for c in xy:
        m = np.where((xy[:, 0] >= c[0] - s / 2) & (xy[:, 0] < c[0] + s / 2) & (xy[:, 1] >= c[1] - s / 2) & (xy[:, 1] < c[1] + s / 2))[0]
        if len(m) and tuple(m) not in seen: seen.add(tuple(m)); wins.append((str(s), m))
CFG = {'A20SH12': ('A25SH12', 0.734), 'A20SH00': ('A25SH00', 0.368)}
FG = np.round(np.arange(0.05, 2.0001, 0.05), 3); fs = 512.0
wind = {}
for k, (w, H) in CFG.items():
    f = [x for x in glob.glob(os.path.join(wdir, '*.mat')) if w in x][0]
    mm = loadmat(f, squeeze_me=True, struct_as_record=False); u = np.asarray(mm['U'], float); fw = float(mm['Settings'].DataRate)
    fr, Su = welch(u - u.mean(), fs=fw, nperseg=20000); U = float(u.mean())
    wind[k] = dict(U=U, H=H, Iu=float(u.std() / U), Su=np.interp(FG * U / H, fr, Su), file=os.path.basename(f))
res = {'fstar_grid': FG.tolist(), 'wind': {k: {kk: vv for kk, vv in v.items() if kk != 'Su'} for k, v in wind.items()}, 'cases': {}}
for f in sorted(glob.glob(os.path.join(root, '*', '*.mat'))):
    grp = os.path.basename(os.path.dirname(f)); w = wind[grp]; U, H = w['U'], w['H']
    P = np.asarray(loadmat(f)['pDataCorrected'], float)
    if P.shape[0] < P.shape[1]: P = P.T
    P = P[:, col]; acc = {}
    for name, idx in wins:
        F = P[:, idx] @ (Ai[idx] / Ai[idx].sum())
        fr, S = welch(F - F.mean(), fs=fs, nperseg=4096)
        bad = np.zeros_like(fr, bool)
        for t in [47.0, 93.75, 187.5, 230.0]: bad |= np.abs(fr - t) <= 0.5
        S = np.where(bad, np.interp(fr, fr[~bad], S[~bad]), S)
        Ss = median_filter(S, 41, mode='nearest'); fl = np.median(Ss[(fr >= 200) & (fr <= 250)])
        ok = (Ss >= 10 * fl) & (fr > 0.5); flim = float(fr[ok].max()) if ok.any() else 0.0
        fq = FG * U / H
        SF = np.interp(fq, fr, S); SF[fq > flim] = np.nan
        chi2 = SF * U ** 2 / (4 * F.mean() ** 2 * w['Su'])
        Afs = Ai[idx].sum(); chiV = 1 / (1 + (2 * FG * np.sqrt(Afs) / (10 * H)) ** (4 / 3)) ** 2   # 2f√A/U = 2 f* √A/H，A 与 H 都取足尺（H 模型×10）
        acc.setdefault(name, []).append((chi2, chiV, Afs))
    summ = {}
    for name, L in acc.items():
        C2 = np.array([a for a, _, _ in L]); CV = np.array([b for _, b, _ in L])
        with np.errstate(all='ignore'):
            summ[name] = dict(n=len(L), area_med_m2=float(np.median([c for _, _, c in L])),
                              chi2_med=[None if not np.isfinite(v) else round(float(v), 5) for v in np.nanmedian(C2, 0)],
                              chi2_p10=[None if not np.isfinite(v) else round(float(v), 5) for v in np.nanpercentile(C2, 10, 0)],
                              chi2_p90=[None if not np.isfinite(v) else round(float(v), 5) for v in np.nanpercentile(C2, 90, 0)],
                              chiV_med=[round(float(v), 5) for v in np.median(CV, 0)],
                              ratio_med=[None if not np.isfinite(v) else round(float(v), 4) for v in np.nanmedian(C2 / CV, 0)])
    res['cases'][os.path.relpath(f, root)] = summ
    print('done', len(res['cases']), flush=True)
json.dump(res, open(os.path.join(out, 'm3_q3_admittance_prj.json'), 'w'))
print('done', len(res['cases']))
