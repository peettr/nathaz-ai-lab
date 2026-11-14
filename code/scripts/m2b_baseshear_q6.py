"""L22.10 M2b（Q1/Q2 预注册响应量 + Q6 + Q1 Shapley），TPU 子集 109 件。跑前写定：
响应量（v1.1 §2.1）：主受力体系顺风向基底剪力 V 与倾覆弯矩 M（只含墙面与屋面水平分力；屋面竖向力对倾覆的贡献不计，报告标明）。
  V_x=Σ_{xneg墙}Cp·A−Σ_{xpos墙}Cp·A＋屋面水平分量；V_y 同理。M=Σ(水平分力×z)。单位 Cp·m²（A 为比值，单位抵消）。
  墙面坐标：沿墙 s=u·(墙长/2)，高 z=v·H0（核过：g120227 端墙 v≤1.75→z≤7 m<屋脊 8.08 m）。从属面积：墙面多边形（山墙含三角）内 0.05 m 网格最近测点。
  屋面水平分量：坡面 p·A_plan·tanθ，方向背离坡面外法线水平分量；双坡按 y 符号定朝向；四坡按最近檐边定朝向；平屋面无。
  顺风向 = |mean| 较大的那个分量（V_x 或 V_y），M 取同方向。
共振增量 A 定义同 M2（00_启动方案 v2 §3.1）：g_B=3.5，g_R/g_B=1.0；σ_R²=(π/4ζ)·f1·S(f1)。
Q6 风速谱法（准定常）：S_F,V(f)=σ_B²·φ_u(f*)/f·χ²(f*)，φ_u=fS_u/σ_u²：von Kármán φ=4x/(1+70.8x²)^{5/6}，Kaimal φ=6.868x/(1+10.302x)^{5/3}，x=f*·L/H，L=100 m（假设）；
  χ²：Vickery 1/[1+(2f*√A_w/H)^{4/3}]²（A_w 迎风面面积）与 χ=1（上限）。即方差按实测 σ_B 标定，只比谱形。
  指标 r(f*)=S_F,V/S_F,测压；A_V 与 A_测压同式。
Shapley（v1.1 §2.2）：基准 n1=1 Hz、ζ=1%、谱=准定常无导纳（Kaimal，χ=1）；三因素换入：频率→n1_act，阻尼→ζ_act，谱→测压积分谱。f*=n1·H/U，U=35 m/s（假设设计风速，屋面高平均风速），另报 U=25/45。
  n1_act∈{4.2,6.0,8.7} Hz，ζ_act∈{0.026,0.072,0.173}（CUREE W-11）。任一组合 f* 超带宽→该组合记 NaN。份额=该因素平均 Δln A / 总 Δln A。
带宽：同 M2（离散滑动平均 |H_d|² 反卷积，增益≤10）。
输出：m2b_tpu.json（每件：均值、σ、带宽、测压谱 φ_F(f*) 于 f* 网格、A 表两法、r、Shapley）。
"""
import sys, os, glob, json, csv, math
import numpy as np
from scipy.io import loadmat
from scipy.signal import welch
from scipy.spatial import cKDTree
root, coordf, out = sys.argv[1:4]; os.makedirs(out, exist_ok=True)
FG = np.round(np.arange(0.02, 3.0001, 0.02), 3)
ZG = [0.01, 0.026, 0.05, 0.072, 0.10, 0.173]; GB = 3.5; LU = 100.0; UD = [25.0, 35.0, 45.0]
N1 = [4.2, 6.0, 8.7]; ZA = [0.026, 0.072, 0.173]
C = {}
for r in csv.DictReader(open(coordf)): C.setdefault((r['lib'], r['case']), []).append(r)

def vor_area(pts, inside, box, g=0.05):
    gx = np.arange(box[0] + g/2, box[1], g); gy = np.arange(box[2] + g/2, box[3], g)
    G = np.stack(np.meshgrid(gx, gy), -1).reshape(-1, 2); G = G[inside(G)]
    idx = cKDTree(pts).query(G)[1]; return np.bincount(idx, minlength=len(pts)) * g * g

def geometry(rows):
    r0 = rows[0]; H0, B, D, th = float(r0['H0']), float(r0['B']), float(r0['D']), math.radians(float(r0['pitch']))
    roof_t = r0['roof']; L, S = max(B, D), min(B, D)   # x 沿长边
    taps = []  # (tap, fx, fy, z)
    for side, length, gable in [('xneg', S, roof_t.startswith('gable')), ('xpos', S, roof_t.startswith('gable')), ('yneg', L, False), ('ypos', L, False)]:
        w = [r for r in rows if r['side'] == side and r['face_type'].startswith('WALL')]
        if not w: continue
        pts = np.array([[float(r['u']) * length / 2, float(r['v']) * H0] for r in w])
        ztop = (lambda s: H0 + np.maximum(0, S/2 - np.abs(s)) * math.tan(th)) if gable else (lambda s: H0 + 0 * s)
        A = vor_area(pts, lambda G: G[:, 1] <= ztop(G[:, 0]), (-length/2, length/2, 0, H0 + S/2 * math.tan(th) + 0.1))
        sgn = 1.0 if side.endswith('neg') else -1.0
        for r, a, p in zip(w, A, pts):
            taps.append((int(r['tap']), sgn * a if side[0] == 'x' else 0.0, sgn * a if side[0] == 'y' else 0.0, p[1]))
    if th > 0:
        rf = [r for r in rows if r['face_type'] == 'ROOF']
        xy = np.array([[float(r['x_fs']), float(r['y_fs'])] for r in rf])
        hx = np.median(np.diff(np.unique(xy[:, 0]))) / 2; hy = np.median(np.diff(np.unique(xy[:, 1]))) / 2
        A = vor_area(xy, lambda G: np.ones(len(G), bool), (xy[:, 0].min() - hx, xy[:, 0].max() + hx, xy[:, 1].min() - hy, xy[:, 1].max() + hy))
        xe, ye = xy[:, 0].max() + hx, xy[:, 1].max() + hy
        for r, a, (x, y) in zip(rf, A, xy):
            ah = a * math.tan(th); z = H0 + max(0.0, S/2 - abs(y)) * math.tan(th)
            if roof_t.startswith('hip') and (xe - abs(x)) < (ye - abs(y)):
                taps.append((int(r['tap']), -math.copysign(ah, x), 0.0, z))   # 端坡朝 ±x，正压推向 ∓x
            else:
                taps.append((int(r['tap']), 0.0, -math.copysign(ah, y), z))
    Aw = {'x': S * H0, 'y': L * H0}
    return taps, H0, Aw

def phi_vk(x): return 4 * x / (1 + 70.8 * x * x) ** (5/6)
def phi_ka(x): return 6.868 * x / (1 + 10.302 * x) ** (5/3)

def A_of(xm, sB, fS_at, z):
    sR2 = math.pi / (4 * z) * fS_at
    return (xm + math.sqrt((GB * sB) ** 2 + GB ** 2 * sR2)) / (xm + GB * sB) - 1

res = {'fstar_grid': FG.tolist(), 'zeta': ZG, 'L_u': LU, 'U_design': UD, 'cases': {}}
for f in sorted(glob.glob(os.path.join(root, '*', '*', '*.mat'))):
    lib, case = f.split(os.sep)[-3], f.split(os.sep)[-2]
    taps, H0, Aw = geometry(C[(lib, case)])
    m = loadmat(f); cp = np.asarray(m['Wind_pressure_coefficients'], float); fs = float(np.squeeze(m['Sample_frequency']))
    H = float(np.squeeze(m['Building_height'])); tapno = np.asarray(m['Location_of_measured_points'])[2].astype(int)
    col = {int(t): j for j, t in enumerate(tapno)}
    miss = [t[0] for t in taps if t[0] not in col]
    if miss: raise SystemExit(f'tap mismatch {lib} {case} {miss[:5]}')
    idx = np.array([col[t[0]] for t in taps]); W = np.array([[t[1], t[2], t[1] * t[3], t[2] * t[3]] for t in taps])
    Vx, Vy, Mx, My = (cp[:, idx] @ W).T
    if abs(Vx.mean()) >= abs(Vy.mean()): V, M, dirn = Vx, Mx, 'x'
    else: V, M, dirn = Vy, My, 'y'
    U_H = 22.0 * (H / 10.0) ** 0.20 if lib == 'noeaves' else 23.4 * (H / 10.0) ** 0.20
    N = 3 if lib == 'noeaves' else 5
    out_c = dict(lib=lib, H=H, H0=H0, along=dirn, n_taps=len(taps))
    for nm, F in [('V', V), ('M', M)]:
        fr, S = welch(F - F.mean(), fs=fs, nperseg=1024)
        Hd2 = np.ones_like(fr); nz = fr > 0
        Hd2[nz] = (np.sin(np.pi * fr[nz] * N / fs) / (N * np.sin(np.pi * fr[nz] / fs))) ** 2
        ok = (1 / np.maximum(Hd2, 1e-12)) <= 10; flim = float(fr[ok & (fr < fs / N)].max())
        Sc = S / np.maximum(Hd2, 1e-12); fst = fr * H / U_H
        xm, sB = abs(F.mean()), F.std()
        phiF = np.interp(np.log(FG), np.log(fst[1:]), (fr * Sc)[1:] / sB ** 2); phiF[FG > flim * H / U_H] = np.nan
        x = FG * LU / H; chi2 = 1 / (1 + (2 * FG * math.sqrt(Aw[dirn]) / H) ** (4/3)) ** 2
        phis = {'vk_chi': phi_vk(x) * chi2, 'ka_chi': phi_ka(x) * chi2, 'vk_1': phi_vk(x), 'ka_1': phi_ka(x)}
        At = {'meas': {}}; [At.setdefault(k, {}) for k in phis]
        for z in ZG:
            At['meas'][str(z)] = [None if not np.isfinite(p) else round(A_of(xm, sB, p * sB ** 2, z), 5) for p in phiF]
            for k, ph in phis.items(): At[k][str(z)] = [round(A_of(xm, sB, p * sB ** 2, z), 5) for p in ph]
        r = {k: [None if not np.isfinite(a) else round(float(b / a), 4) for a, b in zip(phiF, ph)] for k, ph in phis.items()}
        # Shapley
        def phi_meas(fs_): 
            v = np.interp(fs_, FG, np.nan_to_num(phiF, nan=-1)); return v if (fs_ <= flim * H / U_H and v > 0) else float('nan')
        def phi_base(fs_): return phi_ka(fs_ * LU / H)
        sh = {}
        for U in UD:
            for n1 in N1:
                for za in ZA:
                    fb, fa = 1.0 * H / U, n1 * H / U
                    def lnA(fq, zq, spec):
                        fsx = fa if fq else fb; ph = phi_meas(fsx) if spec else phi_base(fsx)
                        if not np.isfinite(ph): return float('nan')
                        a = A_of(xm, sB, ph * sB ** 2, za if zq else 0.01); return math.log(a) if a > 0 else float('nan')
                    import itertools
                    tot = lnA(1, 1, 1) - lnA(0, 0, 0); contrib = [0.0, 0.0, 0.0]; bad = not np.isfinite(tot)
                    for order in itertools.permutations(range(3)):
                        st = [0, 0, 0]
                        for k in order:
                            a0 = lnA(*st); st[k] = 1; a1 = lnA(*st); contrib[k] += (a1 - a0) / 6
                    sh[f'U{int(U)}_n{n1}_z{za}'] = None if bad or not np.isfinite(sum(contrib)) else dict(
                        A_base=round(math.exp(lnA(0, 0, 0)), 5), A_act=round(math.exp(lnA(1, 1, 1)), 5),
                        share_freq=round(contrib[0] / tot, 4), share_damp=round(contrib[1] / tot, 4), share_spec=round(contrib[2] / tot, 4),
                        fstar_act=round(fa, 3))
        out_c[nm] = dict(mean=float(F.mean()), std=float(sB), flim_fstar=float(flim * H / U_H), phiF=[None if not np.isfinite(p) else round(float(p), 6) for p in phiF],
                         A=At, r=r, shapley=sh)
    res['cases'][os.path.relpath(f, root)] = out_c
    print('done', len(res['cases']), flush=True)
json.dump(res, open(os.path.join(out, 'm2b_tpu.json'), 'w'))
print('done', len(res['cases']))
