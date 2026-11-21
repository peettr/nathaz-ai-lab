"""
Generate comparison plots from compare_7lv_lu.py text output.
Parses the per-case R² table and makes figures.
"""
import sys, os, numpy as np, re, subprocess
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path("/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset")

# Run the comparison script and capture output
env = os.environ.copy()
env['PYTHONPATH'] = f"{ROOT}/references:{ROOT}/scripts:{ROOT}/scripts/models"

result = subprocess.run(
    ['/users/[用户]/.conda/envs/graphwind/bin/python', str(ROOT / 'scripts' / 'compare_7lv_lu.py')],
    capture_output=True, text=True, env=env, cwd=str(ROOT)
)
output = result.stdout

# Parse the table
cases = []
r2_5lv = []
r2_7lv = []
r2_lu = []

for line in output.split('\n'):
    # Match lines like: AR-BA-V1_d00  0.2764  0.3812  0.3805  ...
    m = re.match(r'^(\S+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+', line.strip())
    if m:
        cases.append(m.group(1))
        r2_5lv.append(float(m.group(2)))
        r2_7lv.append(float(m.group(3)))
        r2_lu.append(float(m.group(4)))

r5 = np.array(r2_5lv)
r7 = np.array(r2_7lv)
rl = np.array(r2_lu)

print(f"Parsed {len(cases)} cases")

# Classify
idealized_idx = [i for i, c in enumerate(cases) if any(c.startswith(x) for x in ['VA', 'VS', 'UA', 'US'])]
realistic_idx = [i for i, c in enumerate(cases) if i not in idealized_idx]

OUT = ROOT / "results"

# ============ Figure 1: 3-panel comparison ============
fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))

# 1a: 7-level vs Lu
ax = axes[0]
ax.scatter(rl[idealized_idx], r7[idealized_idx], c='#2196F3', s=40, alpha=0.7, label='Idealized', zorder=3)
ax.scatter(rl[realistic_idx], r7[realistic_idx], c='#FF5722', s=40, alpha=0.7, label='Realistic', zorder=3)
lims = [-1, 1.05]
ax.plot(lims, lims, 'k--', lw=1, alpha=0.5)
ax.set_xlabel("Lu et al. R²", fontsize=13)
ax.set_ylabel("Ours (7-level, 1000ep) R²", fontsize=13)
ax.set_xlim(lims); ax.set_ylim(lims)
ax.legend(fontsize=11)
ax.set_title("(a) Per-case R²: Ours vs Lu", fontsize=13)
ax.grid(True, alpha=0.3)

# 1b: 7-level vs 5-level
ax = axes[1]
ax.scatter(r5[idealized_idx], r7[idealized_idx], c='#2196F3', s=40, alpha=0.7, label='Idealized', zorder=3)
ax.scatter(r5[realistic_idx], r7[realistic_idx], c='#FF5722', s=40, alpha=0.7, label='Realistic', zorder=3)
ax.plot(lims, lims, 'k--', lw=1, alpha=0.5)
ax.set_xlabel("5-level R²", fontsize=13)
ax.set_ylabel("7-level R²", fontsize=13)
ax.set_xlim(lims); ax.set_ylim(lims)
ax.legend(fontsize=11)
ax.set_title("(b) Per-case R²: 7-level vs 5-level", fontsize=13)
ax.grid(True, alpha=0.3)

# 1c: R² distribution for realistic cases
ax = axes[2]
bins = np.linspace(-0.5, 1.05, 32)
ax.hist(rl[realistic_idx], bins, alpha=0.5, label=f'Lu (median={np.median(rl[realistic_idx]):.3f})', color='#4CAF50', edgecolor='white')
ax.hist(r7[realistic_idx], bins, alpha=0.5, label=f'Ours (median={np.median(r7[realistic_idx]):.3f})', color='#FF5722', edgecolor='white')
ax.set_xlabel("R²", fontsize=13)
ax.set_ylabel("Count", fontsize=13)
ax.set_title("(c) Realistic R² distribution", fontsize=13)
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(str(OUT / "final_comparison_1000ep.png"), dpi=200, bbox_inches='tight')
print(f"Saved: final_comparison_1000ep.png")

# ============ Figure 2: Bar chart ΔR² ============
fig, ax = plt.subplots(figsize=(16, 6))
delta = r7 - rl
order = np.argsort(delta)
colors = ['#4CAF50' if delta[i] >= 0 else '#F44336' for i in order]
ax.barh(range(len(cases)), delta[order], color=colors, edgecolor='none', height=0.8)
ax.set_yticks(range(len(cases)))
ax.set_yticklabels([cases[i] for i in order], fontsize=5)
ax.axvline(0, color='k', lw=0.8)
ax.set_xlabel("ΔR² (Ours − Lu)", fontsize=13)
ax.set_title("Per-case ΔR²: 7-level (1000ep) vs Lu", fontsize=14)
ax.grid(True, axis='x', alpha=0.3)
n_win = (delta > 0).sum()
n_lose = (delta < 0).sum()
ax.text(0.02, 0.97, f"Win: {n_win}/{len(delta)}  Lose: {n_lose}/{len(delta)}",
        transform=ax.transAxes, fontsize=12, va='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
plt.tight_layout()
fig.savefig(str(OUT / "delta_r2_bar_1000ep.png"), dpi=200, bbox_inches='tight')
print(f"Saved: delta_r2_bar_1000ep.png")

# ============ Figure 3: Training curves ============
fig, ax = plt.subplots(figsize=(8, 5))

for logpath, label, color in [
    (ROOT / "logs" / "uni7lv.log", "7-level 300ep (RTX6K, bs=8)", '#2196F3'),
    (ROOT / "logs" / "uni7h100.log", "7-level 1000ep (A10, bs=16)", '#FF5722')
]:
    epochs, tests = [], []
    with open(str(logpath)) as f:
        for line in f:
            if "Epoch" in line and "test=" in line:
                m2 = re.match(r'.*Epoch\s+(\d+)/\d+.*test=([\d.]+)', line)
                if m2:
                    ep = int(m2.group(1))
                    tl = float(m2.group(2))
                if ep is not None and tl is not None:
                    epochs.append(ep)
                    tests.append(tl)
    ax.plot(epochs, tests, label=label, color=color, lw=1.5)

ax.set_xlabel("Epoch", fontsize=13)
ax.set_ylabel("Test Loss", fontsize=13)
ax.set_title("Training Curves: 7-level UNet", fontsize=14)
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)
ax.set_ylim(bottom=0.07)
plt.tight_layout()
fig.savefig(str(OUT / "training_curves_comparison.png"), dpi=200, bbox_inches='tight')
print(f"Saved: training_curves_comparison.png")

print("\nDone!")
