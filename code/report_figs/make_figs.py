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

B = pathlib.Path(sys.argv[1]); M = B / "model"; S = M / "selfcheck"; O = pathlib.Path(__file__).parent
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
add_sc("S2", "原场景 · fp32", S / "final_v7/S2_v7.npz")
add_sc("S1", "原场景 · bf16", S / "final_v7/S1_v7.npz")
add_sc("T2", "去障碍 · 溃坝初场 · fp32", S / "final_v10_retry/T2_v10.npz")
add_sc("T1", "训练容器 · 静止格点 · fp32", S / "final_v10_retry/T1_v10.npz")
for key, lab in [("H2", "我方 3 m 水箱 h=0.6 · bf16"), ("H1", "我方 3 m 水箱 h=0.3 · bf16")]:
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
ax.axvline(6, color="#8a8984", lw=1, ls=":"); ax.text(6.2, 50, "训练序列长度 6 s", color="#52514e", fontsize=8)
ax.set_xlabel("时间 (s)"); ax.set_ylabel("穿出容器的粒子比例 (%)"); ax.set_xlim(0, 31); ax.set_ylim(-3, 103)
ax.grid(True, axis="y", lw=0.6); ax.legend(frameon=False, fontsize=8, loc="center right")
ax.set_title("图1  各配置静水 / 落水后粒子越界比例随时间", loc="left", fontsize=11)
fig.text(0.01, 0.005, "数据：L26.19 Colab rollout（WorldParticle fancy_fluid 权重，HF wclw1021/WorldParticle，MIT）", fontsize=7, color="#52514e")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(O / "fig1_越界比例.png"); plt.close(fig)

# 图2 每粒子动能（对数）
fig, ax = plt.subplots(figsize=(8, 4.2))
for i, c in enumerate(cfg):
    k = np.where(c["ke"] > 0, c["ke"], np.nan)
    ax.semilogy(c["t"], k, color=C[i], ls=LS[i], lw=2, label=c["label"])
ax.axvline(6, color="#8a8984", lw=1, ls=":")
ax.set_xlabel("时间 (s)"); ax.set_ylabel("每粒子动能 (J，对数轴)"); ax.set_xlim(0, 31)
ax.grid(True, axis="y", lw=0.6, which="major"); ax.legend(frameon=False, fontsize=8, loc="lower right")
ax.set_title("图2  每粒子动能：稳定配置衰减到约 10⁻³ J，失稳配置高出 2–5 个量级", loc="left", fontsize=11)
fig.text(0.01, 0.005, "动能 = 0.5·m·Σ|v|² / N，m=0.3242 kg（训练样本粒子质量）", fontsize=7, color="#52514e")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(O / "fig2_动能.png"); plt.close(fig)

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
        if inside < 0.02: a.text(0.5, 0.5, "粒子已全部飞出视窗", transform=a.transAxes, ha="center", fontsize=8, color="#52514e")
        if j == 0: a.set_ylabel("y (m)", fontsize=8)
        if r == len(rows) - 1: a.set_xlabel("x (m)", fontsize=8)
fig.suptitle("图3  侧视快照（x–y 投影，深灰线为容器底与端墙；超出即穿壁）", x=0.01, ha="left", fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.97)); fig.savefig(O / "fig3_侧视快照.png"); plt.close(fig)

# 图4 P1 复现误差
d = np.load(S / "final_v3/P1_validation_v3.npz"); k = np.arange(1, 600)
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(k, d["author_truth_mse"], color=C[0], lw=2, label="作者 inference.py 对真值")
ax.plot(k, d["custom_truth_mse"], color=C[1], lw=2, ls="--", label="本线手写循环对真值")
ax.plot(k, d["paths_mse"], color=C[2], lw=2, ls="-.", label="两路径之间")
for i, (y, lab) in enumerate([(d["author_truth_mse"][-1], "作者"), (d["custom_truth_mse"][-1], "手写"), (d["paths_mse"][-1], "两路径")]):
    ax.text(603, y, lab, fontsize=8, color="#52514e", va="center")
ax.set_xlabel("推进步数 k（Δt = 0.01 s）"); ax.set_ylabel("位置 MSE (m²)"); ax.grid(True, axis="y", lw=0.6)
ax.legend(frameon=False, fontsize=8); ax.set_xlim(0, 640)
ax.set_title("图4  训练原场景（验证样本 66，bf16）复现误差", loc="left", fontsize=11)
fig.tight_layout(); fig.savefig(O / "fig4_复现误差.png"); plt.close(fig)
OUT["P1"] = dict(author_k100=float(d["author_truth_mse"][99]), custom_k100=float(d["custom_truth_mse"][99]),
                 author_k599=float(d["author_truth_mse"][-1]), paths_k599=float(d["paths_mse"][-1]))

# 图5 feats 取值
tab = json.load(open(S / "sample_table_v5.json"))
ids = [t["id"] for t in tab]; vals = [t["feats_value"] for t in tab]
fig, ax = plt.subplots(figsize=(8, 3.4))
ax.bar(range(len(ids)), vals, color=C[0], width=0.6)
ax.axhline(0, color="#52514e", lw=0.8); ax.axhline(-0.157, color=C[1], lw=1.5, ls="--")
ax.text(len(ids) - 0.5, -0.157, "样本 66 取值 −0.157", color="#52514e", fontsize=8, ha="right", va="bottom")
for i, v in enumerate(vals): ax.text(i, v + (0.01 if v >= 0 else -0.03), f"{v:.3f}", ha="center", fontsize=7, color="#52514e")
ax.set_xticks(range(len(ids)), [f"#{i}" for i in ids]); ax.set_ylabel("loader 后 feats 常数")
ax.set_title("图5  10 个训练样本的粒子特征取值（样本内密度标准化的舍入噪声，含 0）", loc="left", fontsize=11)
fig.tight_layout(); fig.savefig(O / "fig5_feats取值.png"); plt.close(fig)
OUT["feats"] = dict(zip(ids, vals))

# 图6 Colab 用量
rounds = [("01b 28工况", 4.576), ("01c-1 缺dash", 1.436), ("01c-2 帧数断言", 1.103), ("01d 管线自检", 0.962),
          ("01e 断言中止", 0.849), ("01f feats", 0.921), ("01g 分布内两测", 0.682), ("01h 原函数/fp32", 1.035),
          ("01i 闸门止损", 0.759), ("01j fp32 格点", 1.090), ("01k T1/T2", 1.826)]
fail = {"01c-1 缺dash", "01c-2 帧数断言", "01e 断言中止", "01i 闸门止损"}
fig, ax = plt.subplots(figsize=(8, 4))
cols = [C[1] if r in fail else C[0] for r, _ in rounds]
ax.barh(range(len(rounds)), [v for _, v in rounds], color=cols, height=0.6)
for i, (r, v) in enumerate(rounds): ax.text(v + 0.05, i, f"{v:.2f}", va="center", fontsize=8, color="#52514e")
ax.set_yticks(range(len(rounds)), [r for r, _ in rounds], fontsize=8); ax.invert_yaxis()
ax.set_xlabel("Colab CU（按会话时长×费率估，非实扣）")
tot = sum(v for _, v in rounds); waste = sum(v for r, v in rounds if r in fail)
ax.set_title(f"图6  各轮 Colab 用量：合计 ≈{tot:.1f} CU，其中执行问题未出数 ≈{waste:.1f} CU（橙）", loc="left", fontsize=11)
fig.tight_layout(); fig.savefig(O / "fig6_算力用量.png"); plt.close(fig)
OUT["colab_total"] = tot; OUT["colab_waste"] = waste

json.dump(OUT, open(O / "fig_numbers.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(OUT, ensure_ascii=False, indent=1))
