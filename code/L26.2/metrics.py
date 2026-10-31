"""L26.2 风场评价指标对比：对同一真值场的多个候选，算 M1–M6（定义见项目页，10-19 17:40 写定）。

用法：python -I metrics.py <pairs.json> <out_dir>
pairs.json: [{"group": "...", "time": "...", "truth": "t.npy", "cands": {"bilinear": "a.npy", "model": "b.npy"}}, ...]
每个 .npy 为二维风速场（真值网格），NaN 表示建筑/无效格点。
"""
import json, sys, itertools
import numpy as np
from scipy import ndimage, stats

PCTS = (90, 95, 99)
MIN_AREA = 9
STRUCT8 = np.ones((3, 3), int)


def m_pointwise(t, c, valid):
    d = (c - t)[valid]
    mse = float(np.mean(d ** 2))
    rng = float(np.nanmax(t) - np.nanmin(t))
    out = {"RMSE": mse ** 0.5, "PSNR": 10 * np.log10(rng ** 2 / mse) if mse > 0 else np.inf}
    tt, cc = np.where(valid, t, -np.inf), np.where(valid, c, -np.inf)
    it, ic = np.unravel_index(np.argmax(tt), t.shape), np.unravel_index(np.argmax(cc), t.shape)
    out["PeakErr"] = abs(float(cc[ic] - tt[it]))
    out["PeakShift"] = float(np.hypot(it[0] - ic[0], it[1] - ic[1]))
    return out


def m_regions(t, c, valid, pct):
    tau = np.nanpercentile(t[valid], pct)
    bt, bc = (t >= tau) & valid, (c >= tau) & valid
    lt, nt = ndimage.label(bt, STRUCT8)
    lc, nc = ndimage.label(bc, STRUCT8)
    at = ndimage.sum(bt, lt, range(1, nt + 1))
    ac = ndimage.sum(bc, lc, range(1, nc + 1))
    sig_t = [i + 1 for i, a in enumerate(at) if a >= MIN_AREA]
    sig_c = [i + 1 for i, a in enumerate(ac) if a >= MIN_AREA]
    cover = [float((bc & (lt == k)).sum() / (lt == k).sum()) for k in sig_t]
    false = sum(1 for k in sig_c if (bt & (lc == k)).sum() / (lc == k).sum() < 0.10)
    return {f"Reg{pct}_nTrue": len(sig_t), f"Reg{pct}_nCand": len(sig_c),
            f"Reg{pct}_AreaRelErr": abs(float(bc.sum() - bt.sum())) / max(bt.sum(), 1),
            f"Reg{pct}_Hit": float(np.mean([x >= 0.5 for x in cover])) if cover else np.nan,
            f"Reg{pct}_MinCover": min(cover) if cover else np.nan,
            f"Reg{pct}_False": false, f"_cover{pct}": cover}


def superlevel_pd0(f, valid):
    """风速 superlevel 0 维持久图 = (−s) 的 sublevel；无效格点设为 +inf（最后进入）。"""
    import gudhi
    g = np.where(valid, -f, np.nanmax(-f[valid]) + 1e-6)
    cc = gudhi.CubicalComplex(top_dimensional_cells=g)
    cc.compute_persistence()
    d = np.array(cc.persistence_intervals_in_dimension(0))
    d = d[np.isfinite(d).all(axis=1)] if len(d) else np.zeros((0, 2))
    return d


def m_topo(t, c, valid, k=20):
    import gudhi
    from gudhi.hera import wasserstein_distance  # hera 实现，不依赖 POT
    dt, dc = superlevel_pd0(t, valid), superlevel_pd0(c, valid)
    out = {"PD_bottleneck": float(gudhi.bottleneck_distance(dt, dc)),
           "PD_W2": float(wasserstein_distance(dt, dc, order=2, internal_p=np.inf))}
    pt = np.sort(dt[:, 1] - dt[:, 0])[::-1][:k] if len(dt) else np.zeros(0)
    pc = np.sort(dc[:, 1] - dc[:, 0])[::-1][:k] if len(dc) else np.zeros(0)
    pt, pc = np.pad(pt, (0, k - len(pt))), np.pad(pc, (0, k - len(pc)))
    out["MTproxy_topkPersL2"] = float(np.linalg.norm(pt - pc))  # 代理，非原文 TTK 融合树距离
    return out


# 方向：True=越小越好
LOWER = {"RMSE": True, "PSNR": False, "PeakErr": True, "PeakShift": True,
         "PD_bottleneck": True, "PD_W2": True, "MTproxy_topkPersL2": True}
for p in PCTS:
    LOWER.update({f"Reg{p}_AreaRelErr": True, f"Reg{p}_Hit": False, f"Reg{p}_False": True})


def main(pairs_json, out_dir):
    import os
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for p in json.load(open(pairs_json)):
        t = np.load(p["truth"]).astype(float)
        for name, path in p["cands"].items():
            c = np.load(path).astype(float)
            assert c.shape == t.shape, (p["group"], name, c.shape, t.shape)
            valid = np.isfinite(t) & np.isfinite(c)
            r = {"group": p["group"], "time": p.get("time", ""), "cand": name}
            r.update(m_pointwise(t, c, valid))
            for pct in PCTS:
                r.update(m_regions(t, c, valid, pct))
            r.update(m_topo(t, c, valid))
            rows.append(r)
    json.dump(rows, open(f"{out_dir}/per_field.json", "w"), indent=1, default=float)
    summarize(rows, out_dir)


def summarize(rows, out_dir):
    """逐组、逐候选对：每个指标的胜场比例与符号检验；单场时用相对差 ≥5%。"""
    lines = []
    groups = sorted({r["group"] for r in rows})
    for g in groups:
        gr = [r for r in rows if r["group"] == g]
        cands = sorted({r["cand"] for r in gr})
        times = sorted({r["time"] for r in gr})
        for a, b in itertools.combinations(cands, 2):
            for m, low in LOWER.items():
                wa = wb = 0
                rel = []
                for tm in times:
                    ra = next(r for r in gr if r["cand"] == a and r["time"] == tm)
                    rb = next(r for r in gr if r["cand"] == b and r["time"] == tm)
                    xa, xb = ra[m], rb[m]
                    if xa is None or xb is None or np.isnan(xa) or np.isnan(xb) or xa == xb:
                        continue
                    better_a = (xa < xb) if low else (xa > xb)
                    wa += better_a
                    wb += not better_a
                    den = max(abs(xa), abs(xb))
                    rel.append(abs(xa - xb) / den if den else 0)
                n = wa + wb
                pval = stats.binomtest(wa, n).pvalue if n else np.nan
                lines.append({"group": g, "A": a, "B": b, "metric": m, "n": n, "winA": wa, "winB": wb,
                              "shareA": wa / n if n else np.nan, "p": pval,
                              "medRelDiff": float(np.median(rel)) if rel else np.nan})
    json.dump(lines, open(f"{out_dir}/pairwise.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
