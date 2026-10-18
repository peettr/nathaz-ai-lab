"""
Plot R² comparison figures: 7-level (1000ep) vs Lu, 7-level vs 5-level.
"""
import sys, os, numpy as np, re, subprocess
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path("/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset")

# Run comparison script and parse output
env = os.environ.copy()
env['PYTHONPATH'] = f"{ROOT}/references:{ROOT}/scripts:{ROOT}/scripts/models"

result = subprocess.run(
    ['/users/[用户]/.conda/envs/graphwind/bin/python', str(ROOT / 'scripts' / 'compare_7lv_lu.py')],
    capture_output=True, text=True, env=env, cwd=str(ROOT)
)
output = result.stdout

cases = []
r2_5lv = []
r2_7lv = []
r2_lu = []

for line in output.split('\n'):
    m = re.match(r'^(\S+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+', line.strip())
    if m:
        cases.append(m.group(1))
        r2_5lv.append(float(m.group(2)))
        r2_7lv.append(float(m.group(3)))
        r2_lu.append(float(m.group(4)))

r5 = np.array(r2_5lv)
r7 = np.array(r2_7lv)
rl = np.array(r2_lu)

# Classify
idealized_idx = [i for i, c in enumerate(cases) if any(c.startswith(x) for x in ['VA', 'VS', 'UA', 'US'])]
realistic_idx = [i for i, c in enumerate(cases) if i not in idealized_idx]

OUT = ROOT / "results"

# ============ Figure 1: R2 scatter - Ours vs Lu ============
fig, ax = plt.subplots(figsize=(7, 7))

ax.scatter(rl[idealized_idx], r7[idealized_idx], c='#2196F3', s=50, alpha=0.8,
           label=f'Idealized (n={len(idealized_idx)})', zorder=3, edgecolors='white', linewidth=0.5)
ax.scatter(rl[realistic_idx], r7[realistic_idx], c='#FF5722', s=50, alpha=0.8,
           label=f'Realistic (n={len(realistic_idx)})', zorder=3, edgecolors='white', linewidth=0.5)

lims = [-0.8, 1.05]
ax.plot(lims, lims, 'k--', lw=1.2, alpha=0.6, label='y = x')
ax.fill_between(lims, lims, [l-0.1 for l in lims], alpha=0.08, color='green')
ax.fill_between(lims, lims, [l+0.1 for l in lims], alpha=0.08, color='red')

# Annotate outliers
for i in range(len(cases)):
    if abs(r7[i] - rl[i]) > 0.25:
        ax.annotate(cases[i], (rl[i], r7[i]), fontsize=5, alpha=0.7,
                    textcoords="offset points", xytext=(5, 3))

# Stats
n_win = (r7 > rl).sum()
n_lose = (r7 < rl).sum()
global_r2_ours = 1 - np.sum((r7 - rl)**2) / np.sum((rl - rl.mean())**2)  # not meaningful this way
textstr = f'Ours win: {n_win}/{len(cases)}\nLu win: {n_lose}/{len(cases)}\nMedian ΔR²: {np.median(r7-rl):+.3f}'
props = dict(boxstyle='round', facecolor='wheat', alpha=0.9)
ax.text(0.03, 0.97, textstr, transform=ax.transAxes, fontsize=11, verticalalignment='top', bbox=props)

ax.set_xlabel("Lu et al. R²", fontsize=14)
ax.set_ylabel("Ours (7-level, 1000ep) R²", fontsize=14)
ax.set_title("Per-case R²: Ours vs Lu et al.", fontsize=15, fontweight='bold')
ax.set_xlim(lims); ax.set_ylim(lims)
ax.set_aspect('equal')
ax.legend(loc='lower right', fontsize=11)
ax.grid(True, alpha=0.3)
plt.tight_layout()
fig.savefig(str(OUT / "r2_scatter_ours_vs_lu.png"), dpi=200, bbox_inches='tight')
print("Saved: r2_scatter_ours_vs_lu.png")
plt.close(fig)

# ============ Figure 2: R2 scatter - 7-level vs 5-level ============
fig, ax = plt.subplots(figsize=(7, 7))

ax.scatter(r5[idealized_idx], r7[idealized_idx], c='#2196F3', s=50, alpha=0.8,
           label=f'Idealized (n={len(idealized_idx)})', zorder=3, edgecolors='white', linewidth=0.5)
ax.scatter(r5[realistic_idx], r7[realistic_idx], c='#FF5722', s=50, alpha=0.8,
           label=f'Realistic (n={len(realistic_idx)})', zorder=3, edgecolors='white', linewidth=0.5)

ax.plot(lims, lims, 'k--', lw=1.2, alpha=0.6, label='y = x')

textstr = f'7-level better: {( r7>r5).sum()}/{len(cases)}\nMedian ΔR²: {np.median(r7-r5):+.3f}'
ax.text(0.03, 0.97, textstr, transform=ax.transAxes, fontsize=11, verticalalignment='top', bbox=props)

ax.set_xlabel("5-level R²", fontsize=14)
ax.set_ylabel("7-level R²", fontsize=14)
ax.set_title("Per-case R²: 7-level vs 5-level UNet", fontsize=15, fontweight='bold')
ax.set_xlim(lims); ax.set_ylim(lims)
ax.set_aspect('equal')
ax.legend(loc='lower right', fontsize=11)
ax.grid(True, alpha=0.3)
plt.tight_layout()
fig.savefig(str(OUT / "r2_scatter_7lv_vs_5lv.png"), dpi=200, bbox_inches='tight')
print("Saved: r2_scatter_7lv_vs_5lv.png")
plt.close(fig)

# ============ Figure 3: R2 distribution ============
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# 3a: All cases
ax = axes[0]
bins = np.linspace(-0.8, 1.05, 40)
ax.hist(r7, bins, alpha=0.6, label=f'Ours 7-lv (median={np.median(r7):.3f})', color='#FF5722', edgecolor='white')
ax.hist(rl, bins, alpha=0.6, label=f'Lu (median={np.median(rl):.3f})', color='#4CAF50', edgecolor='white')
ax.hist(r5, bins, alpha=0.4, label=f'Ours 5-lv (median={np.median(r5):.3f})', color='#2196F3', edgecolor='white')
ax.set_xlabel("R²", fontsize=13)
ax.set_ylabel("Count", fontsize=13)
ax.set_title("(a) All test cases", fontsize=13)
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)

# 3b: Realistic only
ax = axes[1]
ax.hist(r7[realistic_idx], bins, alpha=0.6, label=f'Ours 7-lv (median={np.median(r7[realistic_idx]):.3f})', color='#FF5722', edgecolor='white')
ax.hist(rl[realistic_idx], bins, alpha=0.6, label=f'Lu (median={np.median(rl[realistic_idx]):.3f})', color='#4CAF50', edgecolor='white')
ax.hist(r5[realistic_idx], bins, alpha=0.4, label=f'Ours 5-lv (median={np.median(r5[realistic_idx]):.3f})', color='#2196F3', edgecolor='white')
ax.set_xlabel("R²", fontsize=13)
ax.set_ylabel("Count", fontsize=13)
ax.set_title("(b) Realistic cases only", fontsize=13)
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(str(OUT / "r2_distribution.png"), dpi=200, bbox_inches='tight')
print("Saved: r2_distribution.png")
plt.close(fig)

# ============ Figure 4: ΔR2 bar chart sorted ============
fig, axes = plt.subplots(2, 1, figsize=(16, 10), gridspec_kw={'height_ratios': [1, 1]})

# 4a: vs Lu
ax = axes[0]
delta_lu = r7 - rl
order_lu = np.argsort(delta_lu)
colors_lu = ['#4CAF50' if delta_lu[i] >= 0 else '#F44336' for i in order_lu]
ax.barh(range(len(cases)), delta_lu[order_lu], color=colors_lu, edgecolor='none', height=0.85)
ax.set_yticks(range(len(cases)))
ax.set_yticklabels([cases[i] for i in order_lu], fontsize=5)
ax.axvline(0, color='k', lw=0.8)
ax.set_xlabel("ΔR² (Ours − Lu)", fontsize=12)
ax.set_title("ΔR²: 7-level (1000ep) vs Lu et al.", fontsize=13, fontweight='bold')
ax.grid(True, axis='x', alpha=0.3)
n_w = (delta_lu > 0).sum()
ax.text(0.02, 0.97, f"Win {n_w}/{len(delta_lu)}", transform=ax.transAxes, fontsize=11, va='top',
        bbox=dict(boxstyle='round', facecolor='lightgreen' if n_w > len(delta_lu)/2 else 'lightyellow', alpha=0.9))

# 4b: vs 5-level
ax = axes[1]
delta_5 = r7 - r5
order_5 = np.argsort(delta_5)
colors_5 = ['#2196F3' if delta_5[i] >= 0 else '#FF9800' for i in order_5]
ax.barh(range(len(cases)), delta_5[order_5], color=colors_5, edgecolor='none', height=0.85)
ax.set_yticks(range(len(cases)))
ax.set_yticklabels([cases[i] for i in order_5], fontsize=5)
ax.axvline(0, color='k', lw=0.8)
ax.set_xlabel("ΔR² (7-level − 5-level)", fontsize=12)
ax.set_title("ΔR²: 7-level vs 5-level", fontsize=13, fontweight='bold')
ax.grid(True, axis='x', alpha=0.3)
n_w5 = (delta_5 > 0).sum()
ax.text(0.02, 0.97, f"7-lv better {n_w5}/{len(delta_5)}", transform=ax.transAxes, fontsize=11, va='top',
        bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.9))

plt.tight_layout()
fig.savefig(str(OUT / "r2_delta_bars.png"), dpi=200, bbox_inches='tight')
print("Saved: r2_delta_bars.png")
plt.close(fig)

# ============ Figure 5: R2 CDF ============
fig, ax = plt.subplots(figsize=(8, 6))

for data, label, color, ls in [
    (r7, f'Ours 7-lv (median={np.median(r7):.3f})', '#FF5722', '-'),
    (rl, f'Lu et al. (median={np.median(rl):.3f})', '#4CAF50', '--'),
    (r5, f'Ours 5-lv (median={np.median(r5):.3f})', '#2196F3', ':'),
]:
    sorted_r2 = np.sort(data)
    cdf = np.arange(1, len(sorted_r2)+1) / len(sorted_r2)
    ax.plot(sorted_r2, cdf, label=label, color=color, linestyle=ls, lw=2)

ax.set_xlabel("R²", fontsize=14)
ax.set_ylabel("Cumulative fraction", fontsize=14)
ax.set_title("R² Cumulative Distribution", fontsize=15, fontweight='bold')
ax.legend(fontsize=11, loc='lower right')
ax.grid(True, alpha=0.3)
ax.set_xlim(-0.8, 1.05)
ax.set_ylim(0, 1.05)
plt.tight_layout()
fig.savefig(str(OUT / "r2_cdf.png"), dpi=200, bbox_inches='tight')
print("Saved: r2_cdf.png")
plt.close(fig)

print("\nDone!")
