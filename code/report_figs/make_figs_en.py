"""L26.19 详版结题报告配图。只读已拉回的小 npz/json，图写到本目录。
用法: python3 -I make_figs.py <L26.19 日志目录>
"""
import json, sys, pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

for f in ["./Windows/Fonts/NotoSansSC-VF.ttf", "./Windows/Fonts/msyh.ttc", "./Windows/Fonts/simsun.ttc"]:
    if pathlib.Path(f).exists():
        fm.fontManager.addfont(f)
        plt.rcParams["font.family"] = fm.FontProperties(fname=f).get_name()
        break
plt.rcParams.update({"axes.unicode_minus": False, "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#52514e", "axes.labelcolor": "#0b0b0b",
                     "xtick.color": "#52514e", "ytick.color": "#52514e", "grid.color": "#e4e3df",
                     "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "savefig.dpi": 160})
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
LS = ["-", "--", "-.", ":", (0, (5, 1, 1, 1)), (0, (3, 1))]

B = pathlib.Path(sys.argv[1]); M = B / "model"; S = M / "selfcheck"; O = pathlib.Path(__file__).parent / "en"
OUT = {}

def box_oob(X, lo, hi):
    return ((X < lo) | (X > hi)).any(-1).sum(-1)

# 六个主配置：时间、越界比例、每粒子动能
cfg = []
def add_sc(key, label, f):
    d = np.load(f)
    n = d["position"].shape[1]
    cfg.append(dict(key=key, label=label, t=d["metric_time"], oob=d["outside"] / n,
                    ke=d["kinetic_energy"] / n, my=d["mean_y"], n=n, pos=d["position"],
                    pt=d["sample_steps"] * 0.01))
add_sc("S2", "Training scene · fp32", S / "final_v7/S2_v7.npz")
add_sc("S1", "Training scene · bf16", S / "final_v7/S1_v7.npz")
add_sc("T2", "Obstacles removed · dam-break · fp32", S / "final_v10_retry/T2_v10.npz")
add_sc("T1", "Training box · still lattice · fp32", S / "final_v10_retry/T1_v10.npz")
for key, lab in [("H2", "Our 3 m tank h=0.6 · bf16"), ("H1", "Our 3 m tank h=0.3 · bf16")]:
    d = np.load(M / f"{key}_G0.npz")
    P, V, m = d["position"], d["velocity"], float(d["particle_mass"])
    lo = np.array([-1.5, 0, -0.25]); hi = np.array([1.5, 1.5, 0.25])
    n = P.shape[1]
    cfg.append(dict(key=key, label=lab, t=d["sample_t"], oob=box_oob(P, lo, hi) / n,
                    ke=0.5 * m * (V ** 2).sum(-1).sum(-1) / n, my=P[:, :, 1].mean(1), n=n, pos=P, pt=d["sample_t"]))

def first_oob(c):
    i = np.nonzero(c["oob"] > 0)[0]
    return None if len(i) == 0 else float(c["t"][i[0]])
OUT["configs"] = [dict(key=c["key"], label=c["label"], n=int(c["n"]), first_oob_s=first_oob(c),
                       oob_frac_end=float(c["oob"][-1]), t_end=float(c["t"][-1])) for c in cfg]

# 图1 越界比例
fig, ax = plt.subplots(figsize=(8, 4.2))
for i, c in enumerate(cfg):
    ax.plot(c["t"], 100 * c["oob"], color=C[i], ls=LS[i], lw=2, label=c["label"])
ax.axvline(6, color="#8a8984", lw=1, ls=":"); ax.text(6.2, 50, "training sequence length 6 s", color="#52514e", fontsize=8)
ax.set_xlabel("Time (s)"); ax.set_ylabel("Particles outside container (%)"); ax.set_xlim(0, 31); ax.set_ylim(-3, 103)
ax.grid(True, axis="y", lw=0.6); ax.legend(frameon=False, fontsize=8, loc="center right")
ax.set_title("Fig. 1  Fraction of particles leaving the container", loc="left", fontsize=11)
fig.text(0.01, 0.005, "Data: L26.19 Colab rollouts (WorldParticle fancy_fluid weights, HF wclw1021/WorldParticle, MIT)", fontsize=7, color="#52514e")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(O / "fig1_out_of_bounds.png"); plt.close(fig)

# 图2 每粒子动能（对数）
fig, ax = plt.subplots(figsize=(8, 4.2))
for i, c in enumerate(cfg):
    k = np.where(c["ke"] > 0, c["ke"], np.nan)
    ax.semilogy(c["t"], k, color=C[i], ls=LS[i], lw=2, label=c["label"])
ax.axvline(6, color="#8a8984", lw=1, ls=":")
ax.set_xlabel("Time (s)"); ax.set_ylabel("Kinetic energy per particle (J, log)"); ax.set_xlim(0, 31)
ax.grid(True, axis="y", lw=0.6, which="major"); ax.legend(frameon=False, fontsize=8, loc="lower right")
ax.set_title("Fig. 2  Kinetic energy per particle: stable case decays to ~1e-3 J; unstable cases 2–5 orders higher", loc="left", fontsize=11)
fig.text(0.01, 0.005, "KE = 0.5·m·Σ|v|² / N, m = 0.3242 kg (training-sample particle mass)", fontsize=7, color="#52514e")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(O / "fig2_kinetic_energy.png"); plt.close(fig)

# 图3 侧视快照
rows = [("S2", [0, 2, 6, 20], (-2, 2), (-0.1, 2.0)), ("T2", [0, 2, 4, 8], (-2, 2), (-0.5, 2.0)),
        ("T1", [0, 0.5, 2, 4], (-2, 2), (-0.5, 1.0)), ("H2", [0, 0.5, 2, 6], (-1.5, 1.5), (-0.5, 1.5))]
byk = {c["key"]: c for c in cfg}
fig, axs = plt.subplots(len(rows), 4, figsize=(11, 9.2))
for r, (k, ts, xl, yl) in enumerate(rows):
    c = byk[k]
    for j, tt in enumerate(ts):
        a = axs[r, j]; idx = int(np.argmin(abs(c["pt"] - tt))); X = c["pos"][idx]
        a.scatter(X[:, 0], X[:, 1], s=0.4, color=C[list(byk).index(k)], rasterized=True)
        a.axhline(0, color="#52514e", lw=0.8); a.axvline(xl[0], color="#52514e", lw=0.8); a.axvline(xl[1], color="#52514e", lw=0.8)
        a.set_xlim(xl[0] - 0.3, xl[1] + 0.3); a.set_ylim(*yl); a.set_aspect("auto")
        a.set_title(f"{c['label']}\nt = {c['pt'][idx]:.1f} s" if j == 0 else f"t = {c['pt'][idx]:.1f} s", fontsize=8, loc="left")
        a.tick_params(labelsize=7)
        inside = ((X[:, 0] > xl[0] - 0.3) & (X[:, 0] < xl[1] + 0.3) & (X[:, 1] > yl[0]) & (X[:, 1] < yl[1])).mean()
        if inside < 0.02: a.text(0.5, 0.5, "all particles left the view", transform=a.transAxes, ha="center", fontsize=8, color="#52514e")
        if j == 0: a.set_ylabel("y (m)", fontsize=8)
        if r == len(rows) - 1: a.set_xlabel("x (m)", fontsize=8)
fig.suptitle("Fig. 3  Side-view snapshots (x–y projection; dark lines = floor and end walls; beyond = wall penetration)", x=0.01, ha="left", fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.97)); fig.savefig(O / "fig3_snapshots.png"); plt.close(fig)

# 图4 P1 复现误差
d = np.load(S / "final_v3/P1_validation_v3.npz"); k = np.arange(1, 600)
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(k, d["author_truth_mse"], color=C[0], lw=2, label="author inference.py vs truth")
ax.plot(k, d["custom_truth_mse"], color=C[1], lw=2, ls="--", label="our loop vs truth")
ax.plot(k, d["paths_mse"], color=C[2], lw=2, ls="-.", label="between the two paths")
for i, (y, lab) in enumerate([(d["author_truth_mse"][-1], "author"), (d["custom_truth_mse"][-1], "ours"), (d["paths_mse"][-1], "paths")]):
    ax.text(603, y, lab, fontsize=8, color="#52514e", va="center")
ax.set_xlabel("Rollout step k (Δt = 0.01 s)"); ax.set_ylabel("Position MSE (m²)"); ax.grid(True, axis="y", lw=0.6)
ax.legend(frameon=False, fontsize=8); ax.set_xlim(0, 640)
ax.set_title("Fig. 4  Reproduction error on the training scene (validation sample 66, bf16)", loc="left", fontsize=11)
fig.tight_layout(); fig.savefig(O / "fig4_reproduction_error.png"); plt.close(fig)
OUT["P1"] = dict(author_k100=float(d["author_truth_mse"][99]), custom_k100=float(d["custom_truth_mse"][99]),
                 author_k599=float(d["author_truth_mse"][-1]), paths_k599=float(d["paths_mse"][-1]))

# 图5 feats 取值
tab = json.load(open(S / "sample_table_v5.json"))
ids = [t["id"] for t in tab]; vals = [t["feats_value"] for t in tab]
fig, ax = plt.subplots(figsize=(8, 3.4))
ax.bar(range(len(ids)), vals, color=C[0], width=0.6)
ax.axhline(0, color="#52514e", lw=0.8); ax.axhline(-0.157, color=C[1], lw=1.5, ls="--")
ax.text(len(ids) - 0.5, -0.157, "sample 66: −0.157", color="#52514e", fontsize=8, ha="right", va="bottom")
for i, v in enumerate(vals): ax.text(i, v + (0.01 if v >= 0 else -0.03), f"{v:.3f}", ha="center", fontsize=7, color="#52514e")
ax.set_xticks(range(len(ids)), [f"#{i}" for i in ids]); ax.set_ylabel("feats constant after loader")
ax.set_title("Fig. 5  Particle feature value in 10 training samples (round-off of per-sample density standardisation; includes 0)", loc="left", fontsize=11)
fig.tight_layout(); fig.savefig(O / "fig5_feats.png"); plt.close(fig)
OUT["feats"] = dict(zip(ids, vals))

# 图6 Colab 用量
rounds = [("01b 28 cases", 4.576), ("01c-1 missing dash", 1.436), ("01c-2 frame assert", 1.103), ("01d pipeline check", 0.962),
          ("01e assert abort", 0.849), ("01f feats", 0.921), ("01g in-dist. tests", 0.682), ("01h author fn/fp32", 1.035),
          ("01i budget gate", 0.759), ("01j fp32 lattice", 1.090), ("01k T1/T2", 1.826)]
fail = {"01c-1 missing dash", "01c-2 frame assert", "01e assert abort", "01i budget gate"}
fig, ax = plt.subplots(figsize=(8, 4))
cols = [C[1] if r in fail else C[0] for r, _ in rounds]
ax.barh(range(len(rounds)), [v for _, v in rounds], color=cols, height=0.6)
for i, (r, v) in enumerate(rounds): ax.text(v + 0.05, i, f"{v:.2f}", va="center", fontsize=8, color="#52514e")
ax.set_yticks(range(len(rounds)), [r for r, _ in rounds], fontsize=8); ax.invert_yaxis()
ax.set_xlabel("Colab CU (session time × rate, estimate, not billed)")
tot = sum(v for _, v in rounds); waste = sum(v for r, v in rounds if r in fail)
ax.set_title(f"Fig. 6  Colab use per round: total ≈{tot:.1f} CU; ≈{waste:.1f} CU lost to execution issues (orange)", loc="left", fontsize=11)
fig.tight_layout(); fig.savefig(O / "fig6_compute.png"); plt.close(fig)
OUT["colab_total"] = tot; OUT["colab_waste"] = waste

json.dump(OUT, open(O / "fig_numbers_en.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(OUT, ensure_ascii=False, indent=1))
