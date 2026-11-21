"""与 run_l262.py 相同的场构造（只用于出图），t 为 t_s 秒数。"""
import numpy as np
from scipy import ndimage
c, m0, m1 = (np.load(f"/content/{n}.npz") for n in ("cm1", "m0", "m1"))
spd = lambda U: np.hypot(U[..., 0], U[..., 1])
ix = np.array([np.argmin(abs(c["x_m"] - x)) for x in m1["x_m"]])
iy = np.array([np.argmin(abs(c["y_m"] - y)) for y in m1["y_m"]])
win = lambda F: F[..., iy[:, None], ix[None, :]]
NAMES = {0: "nearest", 1: "bilinear", 3: "bicubic"}


def interp(f, k, order):
    n = f.shape[0] // k
    coarse = f[:n * k, :n * k].reshape(n, k, n, k).mean(axis=(1, 3))
    return ndimage.zoom(coarse, k, order=order, mode="nearest", grid_mode=True)


def fields(g, tsec):
    t = int(np.argmin(abs(c["t_s"] - tsec)))
    T = spd(c["U50"][t])
    cands = {"M0": spd(m0["U50"][t])}
    for k in (4, 5):
        for o, nm in NAMES.items():
            cands[f"{nm}_c{k}"] = interp(T, k, o)
    if g == "G2_win40":
        T = win(T); cands = {n: win(v) for n, v in cands.items()}; cands["M1"] = spd(m1["U50"][t])
    return T, cands
