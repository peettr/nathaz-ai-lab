"""画"RMSE 更好却漏"实例：真值 / A（RMSE 更好）/ B，叠真值 τ 等值线与显著区。用法：python plot_instance.py <group> <time> <A> <B> <pct>"""
import sys, json
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
g, tm, A, B, pct = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4], int(sys.argv[5])
sys.path.insert(0, "/content")
import run_l262_fields as F  # 只重建场，不重算指标
T, cands = F.fields(g, tm)
tau = np.nanpercentile(T, pct)
rows = {r["cand"]: r for r in json.load(open("/content/out/per_field.json")) if r["group"] == g and r["time"] == tm}
vmax = max(np.nanmax(T), np.nanmax(cands[A]), np.nanmax(cands[B]))
fig, ax = plt.subplots(1, 3, figsize=(13, 4.3), constrained_layout=True)
for a, (nm, f) in zip(ax, (("Reference (CM1)", T), (A, cands[A]), (B, cands[B]))):
    im = a.imshow(f, origin="lower", cmap="viridis", vmin=0, vmax=vmax)
    a.contour(T, [tau], colors="w", linewidths=1.0)
    a.contour(f, [tau], colors="r", linewidths=1.0, linestyles="--")
    sub = "" if nm.startswith("Ref") else f"\nRMSE={rows[nm]['RMSE']:.2f} m/s, hit{pct}={rows[nm][f'Reg{pct}_Hit']:.2f}"
    a.set_title(nm + sub, fontsize=10); a.set_xticks([]); a.set_yticks([])
fig.colorbar(im, ax=ax, shrink=0.8, label="50 m horizontal speed (m/s)")
fig.suptitle(f"{g}, t={tm} s: white = reference P{pct} contour ({tau:.1f} m/s), red dashed = candidate same threshold\n"
             "Data: CM1 line D420 downburst simulation (internal; CM1 job 3372048, CFD M0/M1)", fontsize=9)
fig.savefig(f"/content/out/instance_{g}_t{tm}_{A}_vs_{B}_P{pct}.png", dpi=130)
print("saved")
