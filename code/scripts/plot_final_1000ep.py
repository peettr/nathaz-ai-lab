"""
Generate comparison plots for 7-level 1000ep vs Lu and vs 5-level.
"""
import sys, os, json, numpy as np, torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'references'))

from unet_lu_7level import UNetLu7Level
from data_formatter_fixed import restore_raw_output_data

ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = ROOT / "data" / "full_masked_640"
RESULTS_DIR = ROOT / "results" / "full_masked_640_7level" / "seed_1"
RESULTS_5LV = ROOT / "results" / "full_masked_640" / "seed_1"
LU_METRICS = ROOT / "references" / "all_cases_20exp" / "metrics_in_test_set_seed1.csv"
TEST_CSV = ROOT / "scripts" / "lu_full_test_seed1.csv"

# Load test data
test_data = torch.load(str(DATA_DIR / "test.pt"), map_location="cpu", weights_only=False)
X_test, Y_test = test_data["X"], test_data["Y"]

# Load 7-level model
model7 = UNetLu7Level(n_c=16)
model7.load_state_dict(torch.load(str(RESULTS_DIR / "model_best.pt"), map_location="cpu", weights_only=True))
model7.eval()

# Load 5-level model
from unet_lu import UNetLu
model5 = UNetLu(n_c=16)
model5.load_state_dict(torch.load(str(RESULTS_5LV / "model_best.pt"), map_location="cpu", weights_only=True))
model5.eval()

# Inference
with torch.no_grad():
    pred7 = model7(X_test).numpy()
    pred5 = model5(X_test).numpy()

X_np = X_test.numpy()
Y_np = Y_test.numpy()

# Load case info
import pandas as pd
test_df = pd.read_csv(str(TEST_CSV))
lu_df = pd.read_csv(str(LU_METRICS))

# Build per-case R²
def compute_per_case_r2(pred_all, X_np, Y_np, test_df):
    """Compute R² per case in raw domain."""
    case_r2 = {}
    grouped = test_df.groupby('case_name')
    for case_name, group in grouped:
        indices = group.index.tolist()
        # Collect patches for this case
        all_pred_raw = []
        all_true_raw = []
        for idx in indices:
            patch_pred = pred_all[idx, 0]
            patch_true = Y_np[idx, 0]
            patch_x = X_np[idx, 0]
            
            # Restore to raw domain
            mask = (~np.isnan(patch_true)) & (patch_x <= 0)
            if mask.sum() == 0:
                continue
            
            # Get U_mean for normalization
            pred_raw = restore_raw_output_data(patch_pred, patch_x)
            true_raw = restore_raw_output_data(patch_true, patch_x)
            
            valid = ~np.isnan(true_raw)
            all_pred_raw.append(pred_raw[valid])
            all_true_raw.append(true_raw[valid])
        
        if not all_pred_raw:
            continue
        
        p = np.concatenate(all_pred_raw)
        t = np.concatenate(all_true_raw)
        
        ss_res = np.sum((p - t) ** 2)
        ss_tot = np.sum((t - t.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else -999
        case_r2[case_name] = r2
    
    return case_r2

r2_7lv = compute_per_case_r2(pred7, X_np, Y_np, test_df)
r2_5lv = compute_per_case_r2(pred5, X_np, Y_np, test_df)

# Build Lu R² dict
lu_r2 = {}
for _, row in lu_df.iterrows():
    case = row['case_name']
    lu_r2[case] = row['r2'] if 'r2' in lu_df.columns else row.get('R2', None)

# Match cases
common = sorted(set(r2_7lv.keys()) & set(r2_5lv.keys()) & set(lu_r2.keys()))
r7 = np.array([r2_7lv[c] for c in common])
r5 = np.array([r2_5lv[c] for c in common])
rl = np.array([lu_r2[c] for c in common])

# Classify cases
idealized = [i for i, c in enumerate(common) if any(c.startswith(x) for x in ['VA', 'VS', 'UA', 'US'])]
realistic = [i for i, c in enumerate(common) if i not in idealized]

print(f"Total cases: {len(common)}, idealized: {len(idealized)}, realistic: {len(realistic)}")

OUT = ROOT / "results"

# ============ Figure 1: Scatter plot 7-level vs Lu ============
fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))

# 1a: All cases scatter
ax = axes[0]
ax.scatter(rl[idealized], r7[idealized], c='#2196F3', s=40, alpha=0.7, label='Idealized', zorder=3)
ax.scatter(rl[realistic], r7[realistic], c='#FF5722', s=40, alpha=0.7, label='Realistic', zorder=3)
lims = [-1, 1.05]
ax.plot(lims, lims, 'k--', lw=1, alpha=0.5)
ax.set_xlabel("Lu R²", fontsize=13)
ax.set_ylabel("Ours (7-level) R²", fontsize=13)
ax.set_xlim(lims)
ax.set_ylim(lims)
ax.legend(fontsize=11)
ax.set_title("(a) Per-case R²: Ours vs Lu", fontsize=13)
ax.grid(True, alpha=0.3)

# 1b: 7-level vs 5-level
ax = axes[1]
ax.scatter(r5[idealized], r7[idealized], c='#2196F3', s=40, alpha=0.7, label='Idealized', zorder=3)
ax.scatter(r5[realistic], r7[realistic], c='#FF5722', s=40, alpha=0.7, label='Realistic', zorder=3)
ax.plot(lims, lims, 'k--', lw=1, alpha=0.5)
ax.set_xlabel("5-level R²", fontsize=13)
ax.set_ylabel("7-level R²", fontsize=13)
ax.set_xlim(lims)
ax.set_ylim(lims)
ax.legend(fontsize=11)
ax.set_title("(b) Per-case R²: 7-level vs 5-level", fontsize=13)
ax.grid(True, alpha=0.3)

# 1c: R² distribution
ax = axes[2]
bins = np.linspace(-0.5, 1.05, 32)
ax.hist(rl[realistic], bins, alpha=0.5, label=f'Lu (median={np.median(rl[realistic]):.3f})', color='#4CAF50', edgecolor='white')
ax.hist(r7[realistic], bins, alpha=0.5, label=f'Ours (median={np.median(r7[realistic]):.3f})', color='#FF5722', edgecolor='white')
ax.set_xlabel("R²", fontsize=13)
ax.set_ylabel("Count", fontsize=13)
ax.set_title("(c) Realistic R² distribution", fontsize=13)
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(str(OUT / "final_comparison_1000ep.png"), dpi=200, bbox_inches='tight')
print(f"Saved: {OUT / 'final_comparison_1000ep.png'}")

# ============ Figure 2: Bar chart ΔR² ============
fig, ax = plt.subplots(figsize=(16, 6))
delta = r7 - rl
order = np.argsort(delta)
colors = ['#4CAF50' if d >= 0 else '#F44336' for d in delta[order]]
bars = ax.barh(range(len(common)), delta[order], color=colors, edgecolor='none', height=0.8)
ax.set_yticks(range(len(common)))
ax.set_yticklabels([common[i] for i in order], fontsize=5)
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
print(f"Saved: {OUT / 'delta_r2_bar_1000ep.png'}")

# ============ Figure 3: Training curves comparison ============
fig, ax = plt.subplots(figsize=(8, 5))

# Parse 300ep log
log300 = ROOT / "logs" / "uni7lv.log"
log1000 = ROOT / "logs" / "uni7h100.log"

for logpath, label, color in [(log300, "7-level 300ep (RTX6K, bs=8)", '#2196F3'),
                                (log1000, "7-level 1000ep (A10, bs=16)", '#FF5722')]:
    epochs, tests = [], []
    with open(str(logpath)) as f:
        for line in f:
            if "Epoch" in line and "test=" in line:
                parts = line.strip().split()
                for p in parts:
                    if p.startswith("Epoch"):
                        ep = int(p.split("/")[0].replace("Epoch", "").strip())
                    if p.startswith("test="):
                        tl = float(p.split("=")[1])
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
print(f"Saved: {OUT / 'training_curves_comparison.png'}")

print("\nDone! All figures saved to results/")
