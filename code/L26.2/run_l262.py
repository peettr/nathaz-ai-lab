"""L26.2 主计算：D420 50 m 水平风速（CM1 为参考）上比较候选的各指标排序。
在 Colab CPU 上跑：/content 下需有 metrics.py、cm1.npz、m0.npz、m1.npz。
组 G1（全域 200×200，27 帧）：候选 M0、插值基线 nearest/bilinear/bicubic（CM1 块平均降 4×、5× 后插回）。
组 G2（4 km 窗 40×40，27 帧）：候选 M0、M1、插值基线（全域降采样插回后裁窗）。
"""
import json, sys, itertools, os
import numpy as np
from scipy import ndimage
sys.path.insert(0, "/content")
import metrics as M

OUT = "/content/out"
os.makedirs(OUT, exist_ok=True)
c, m0, m1 = (np.load(f"/content/{n}.npz") for n in ("cm1", "m0", "m1"))
assert np.allclose(c["x_m"], m0["x_m"], atol=1e-3) and np.allclose(c["y_m"], m0["y_m"], atol=1e-3)
assert np.allclose(c["t_s"], m0["t_s"]) and np.allclose(c["t_s"], m1["t_s"])
spd = lambda U: np.hypot(U[..., 0], U[..., 1])  # U50[t, y, x, (u,v,w)]
S_c, S_m0, S_m1 = spd(c["U50"]), spd(m0["U50"]), spd(m1["U50"])
ix = np.array([np.argmin(abs(c["x_m"] - x)) for x in m1["x_m"]])
iy = np.array([np.argmin(abs(c["y_m"] - y)) for y in m1["y_m"]])
assert np.allclose(c["x_m"][ix], m1["x_m"], atol=0.01) and len(set(ix)) == 40 and len(set(iy)) == 40
win = lambda F: F[..., iy[:, None], ix[None, :]]


def interp(f, k, order):
    n = f.shape[0] // k
    coarse = f[:n * k, :n * k].reshape(n, k, n, k).mean(axis=(1, 3))
    return ndimage.zoom(coarse, k, order=order, mode="nearest", grid_mode=True)


NAMES = {0: "nearest", 1: "bilinear", 3: "bicubic"}
rows = []
for t in range(S_c.shape[0]):
    T = S_c[t]
    cands = {"M0": S_m0[t]}
    for k in (4, 5):
        for o, nm in NAMES.items():
            cands[f"{nm}_c{k}"] = interp(T, k, o)
    for g, truth, cc in (("G1_full200", T, cands),
                         ("G2_win40", win(T), {**{n: win(v) for n, v in cands.items()}, "M1": S_m1[t]})):
        valid = np.isfinite(truth)
        for name, f in cc.items():
            r = {"group": g, "time": int(c["t_s"][t]), "cand": name}
            r.update(M.m_pointwise(truth, f, valid))
            for p in M.PCTS:
                r.update(M.m_regions(truth, f, valid, p))
            r.update(M.m_topo(truth, f, valid))
            rows.append(r)
    print("frame", t, flush=True)

json.dump(rows, open(f"{OUT}/per_field.json", "w"), indent=1, default=float)
M.summarize(rows, OUT)

# 找"RMSE 更好却漏"实例（判据：RMSE_A < RMSE_B 且相对差 ≥2%，真值某显著区 A 覆盖 <0.5、B ≥0.5；95 百分位为主）
inst = []
for g in ("G1_full200", "G2_win40"):
    for tm in sorted({r["time"] for r in rows}):
        rr = [r for r in rows if r["group"] == g and r["time"] == tm]
        for a, b in itertools.permutations(rr, 2):
            if not (a["RMSE"] < b["RMSE"] and (b["RMSE"] - a["RMSE"]) / b["RMSE"] >= 0.02):
                continue
            for p in M.PCTS:
                ca, cb = a[f"_cover{p}"], b[f"_cover{p}"]
                miss = [i for i in range(len(ca)) if ca[i] < 0.5 and cb[i] >= 0.5]
                if miss:
                    inst.append({"group": g, "time": tm, "pct": p, "A_rmse_better": a["cand"], "B": b["cand"],
                                 "RMSE_A": a["RMSE"], "RMSE_B": b["RMSE"], "regions_missed_by_A": miss,
                                 "coverA": [ca[i] for i in miss], "coverB": [cb[i] for i in miss]})
json.dump(inst, open(f"{OUT}/rmse_better_but_miss.json", "w"), indent=1, default=float)
print("instances", len(inst))
