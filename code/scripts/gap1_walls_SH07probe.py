"""L22.10 缺口①A（11-27，方案增补写定）：同 m3_q3_walls_prj.py，唯一改动——SH12 的来流改用近墙面高度的 A25SH07 探头（推断高度 19.08 ft 足尺，位于墙面 12–22 ft 之间）作 U 与 S_u；f* 轴仍按屋面 H=0.734 m、U=21.51 m/s 定义以便对照。只算 SH12。
原说明：L22.10 M3 Q3 补：墙面、楼板底面（架空）、屋角的实测气动导纳（预注册 §2 要求迎风墙/屋面/屋角分报；审查 23c6542f 指出未完成）。跑前写定。
定义同 m3_q3_admittance_prj.py：χ²(f)=S_F(f)·U²/(4F̄²S_u(f))；χ²_V=1/[1+(2f*√A/H)^{4/3}]²（A、H 足尺）；比=χ²/χ²_V。
面（坐标为测点表模型英寸，×0.254 得足尺 m）：
  side_L（x=0，坐标 y,z）、side_R（x=30，y,z）、gable（y=0，x,z）、floor（楼板底 z=0，x,y；只取 y≤30 in 的测点——表中 y=55.8–70.55 的 3 点超出半模型范围，疑为录入问题，排除）。
  每面：整面平均 + 边长 2/4 m 足尺方窗（以测点为中心、半开区间）。从属面积：面内测点包络外扩半个中位间距的矩形内 Voronoi（山墙按包络矩形近似，未裁三角——假设）。
  迎风面：每件取整面平均压力均值最大的那一面（只在 side_L/side_R/gable 中选），单独汇总为 windward。
  屋角：屋面测点中平面坐标落在两个山墙端角（x≤7.874 in 或 x≥22.126 in，且 y≤7.874 in；即足尺 2 m×2 m）的测点，每角一个窗。
风速、H、U、尖峰处理、带宽判据与 m3_q3_admittance_prj.py 完全相同。
用法：python m3_q3_walls_prj.py <prj5592_subset根> <taps csv> <wind目录> <输出目录>
"""
import sys, os, glob, json, csv
import numpy as np
from scipy.io import loadmat
from scipy.signal import welch
from scipy.ndimage import median_filter
from scipy.spatial import cKDTree
root, tabf, wdir, out = sys.argv[1:5]; os.makedirs(out, exist_ok=True)
IN = 0.254
rows = list(csv.DictReader(open(tabf)))
def num(v):
    try: return float(v)
    except: return None
def face(sel, ax):
    t = [r for r in rows if sel(r)]
    col = np.array([int(r['col']) - 1 for r in t]); xy = np.array([[num(r[ax[0]]) * IN, num(r[ax[1]]) * IN] for r in t])
    h = [np.median(np.diff(np.unique(xy[:, i]))) / 2 for i in (0, 1)]
    g = 0.02; gx = np.arange(xy[:, 0].min() - h[0] + g / 2, xy[:, 0].max() + h[0], g); gy = np.arange(xy[:, 1].min() - h[1] + g / 2, xy[:, 1].max() + h[1], g)
    G = np.stack(np.meshgrid(gx, gy), -1).reshape(-1, 2); A = np.bincount(cKDTree(xy).query(G)[1], minlength=len(t)) * g * g
    return col, xy, A
F = {'side_L': face(lambda r: r['surface'].strip() == 'Side wall left', ('y_in', 'z_in')),
     'side_R': face(lambda r: r['surface'].strip() == 'Side wall right', ('y_in', 'z_in')),
     'gable': face(lambda r: r['surface'].strip() == 'Gable wall', ('x_in', 'z_in')),
     'floor': face(lambda r: r['surface'].strip() == 'Floor' and num(r['y_in']) is not None and num(r['y_in']) <= 30, ('x_in', 'y_in'))}
roof = [r for r in rows if 'oof' in r['surface']]
rc = np.array([int(r['col']) - 1 for r in roof]); rxy = np.array([[num(r['x_in']), num(r['y_in'])] for r in roof])
rg = 0.02; gg = np.arange(rg / 2, 30 * IN, rg); RG = np.stack(np.meshgrid(gg, gg), -1).reshape(-1, 2)
rA = np.bincount(cKDTree(rxy[:, [1, 0]] * IN).query(RG)[1], minlength=len(roof)) * rg * rg
corners = {'corner_x0': np.where((rxy[:, 0] <= 7.874) & (rxy[:, 1] <= 7.874))[0], 'corner_x30': np.where((rxy[:, 0] >= 22.126) & (rxy[:, 1] <= 7.874))[0]}
wins = []
for fn, (col, xy, A) in F.items():
    wins.append((fn, 'whole', col, A))
    for s in [2.0, 4.0]:
        seen = set()
        for c in xy:
            m = np.where((xy[:, 0] >= c[0] - s / 2) & (xy[:, 0] < c[0] + s / 2) & (xy[:, 1] >= c[1] - s / 2) & (xy[:, 1] < c[1] + s / 2))[0]
            if len(m) and tuple(m) not in seen: seen.add(tuple(m)); wins.append((fn, str(s), col[m], A[m]))
for cn, m in corners.items(): wins.append(('roof_corner', cn, rc[m], rA[m]))
CFG = {'A20SH12': ('A25SH07', 0.734)}; UF = {'A20SH12': 21.51}
FG = np.round(np.arange(0.05, 2.0001, 0.05), 3); fs = 512.0
wind = {}
for k, (w, H) in CFG.items():
    f = [x for x in glob.glob(os.path.join(wdir, '*.mat')) if w in x][0]
    mm = loadmat(f, squeeze_me=True, struct_as_record=False); u = np.asarray(mm['U'], float); fw = float(mm['Settings'].DataRate)
    fr, Su = welch(u - u.mean(), fs=fw, nperseg=20000); U = float(u.mean())
    wind[k] = dict(U=U, H=H, Su=np.interp(FG * UF[k] / H, fr, Su))
res = {'fstar_grid': FG.tolist(), 'n_taps': {k: len(v[0]) for k, v in F.items()}, 'n_corner_taps': {k: len(v) for k, v in corners.items()}, 'cases': {}}
for f in sorted(glob.glob(os.path.join(root, '*', '*.mat'))):
    grp = os.path.basename(os.path.dirname(f))
    if grp not in wind: continue
    w = wind[grp]; U, H = w['U'], w['H']
    P = np.asarray(loadmat(f)['pDataCorrected'], float)
    if P.shape[0] < P.shape[1]: P = P.T
    acc = {}; means = {}
    for fn, wn, col, A in wins:
        Fz = P[:, col] @ (A / A.sum())
        fr, S = welch(Fz - Fz.mean(), fs=fs, nperseg=4096)
        bad = np.zeros_like(fr, bool)
        for t in [47.0, 93.75, 187.5, 230.0]: bad |= np.abs(fr - t) <= 0.5
        S = np.where(bad, np.interp(fr, fr[~bad], S[~bad]), S)
        Ss = median_filter(S, 41, mode='nearest'); fl = np.median(Ss[(fr >= 200) & (fr <= 250)])
        ok = (Ss >= 10 * fl) & (fr > 0.5); flim = float(fr[ok].max()) if ok.any() else 0.0
        fq = FG * UF[grp] / H; SF = np.interp(fq, fr, S); SF[fq > flim] = np.nan
        chi2 = SF * U ** 2 / (4 * Fz.mean() ** 2 * w['Su'])
        chiV = 1 / (1 + (2 * FG * np.sqrt(A.sum()) / (10 * H)) ** (4 / 3)) ** 2
        key = f'{fn}|{wn if wn in ("whole",) or fn == "roof_corner" else wn}'
        acc.setdefault(key, []).append((chi2, chiV, float(A.sum()), float(Fz.mean())))
        if wn == 'whole': means[fn] = float(Fz.mean())
    ww = max(['side_L', 'side_R', 'gable'], key=lambda k: means[k])
    acc['windward|whole'] = acc[f'{ww}|whole']
    for k2 in ['2.0', '4.0']: acc[f'windward|{k2}'] = acc[f'{ww}|{k2}']
    summ = {'windward_face': ww, 'face_means': means}
    for key, L in acc.items():
        C2 = np.array([a for a, _, _, _ in L]); CV = np.array([b for _, b, _, _ in L])
        with np.errstate(all='ignore'):
            summ[key] = dict(n=len(L), area_med_m2=float(np.median([c for _, _, c, _ in L])), mean_med=float(np.median([d for _, _, _, d in L])),
                             chi2_med=[None if not np.isfinite(v) else round(float(v), 5) for v in np.nanmedian(C2, 0)],
                             chiV_med=[round(float(v), 5) for v in np.median(CV, 0)],
                             ratio_med=[None if not np.isfinite(v) else round(float(v), 4) for v in np.nanmedian(C2 / CV, 0)])
    res['cases'][os.path.relpath(f, root)] = summ
    print('done', len(res['cases']), flush=True)
json.dump(res, open(os.path.join(out, 'gap1_walls_SH07probe.json'), 'w'))
print('done', len(res['cases']))
