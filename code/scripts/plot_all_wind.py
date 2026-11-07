"""
Plot spatial wind field predictions for ALL test cases.
"""
import sys, os, numpy as np, torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
import pandas as pd

ROOT = Path("/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset")
sys.path.insert(0, str(ROOT / "references"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "models"))

from unet_lu_7level import UNetLu7Level

# Load test split
test_df = pd.read_csv(str(ROOT / "scripts" / "lu_full_test_seed1.csv"))
lu_df = pd.read_csv(str(ROOT / "references" / "all_cases_20exp" / "metrics_in_test_set_seed1.csv"))
lu_df['case_name'] = lu_df['topo'].astype(str) + '_d' + lu_df['angle'].astype(str).str.zfill(2)

# Load model
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = UNetLu7Level(n_c=16).to(device)
model.load_state_dict(torch.load(str(ROOT / "results" / "full_masked_640_7level" / "seed_1" / "model_best.pt"),
                                   map_location=device, weights_only=True))
model.eval()

# Load test data
test_data = torch.load(str(ROOT / "data" / "full_masked_640" / "test.pt"), map_location=device, weights_only=False)
X_test = test_data["X"]
Y_test = test_data["Y"]

with torch.no_grad():
    pred_all = model(X_test).cpu().numpy()

X_np = X_test.cpu().numpy()
Y_np = Y_test.cpu().numpy()

OUT = ROOT / "results" / "wind_field_plots"
OUT.mkdir(exist_ok=True)

grouped = test_df.groupby('case_name')
all_cases = sorted(grouped.groups.keys())

# Compute per-case R2 for sorting
case_data = []
for case_name in all_cases:
    group = grouped.get_group(case_name)
    idx = group.index[0]
    x_input = X_np[idx, 0]
    gt = Y_np[idx, 0].copy()
    pr = pred_all[idx, 0].copy()
    mask = (~np.isnan(gt)) & (x_input <= 0)
    if mask.sum() > 0:
        ss_res = np.sum((pr[mask] - gt[mask])**2)
        ss_tot = np.sum((gt[mask] - gt[mask].mean())**2)
        r2 = 1 - ss_res/ss_tot if ss_tot > 0 else -999
    else:
        r2 = -999
    lu_row = lu_df[lu_df['case_name'] == case_name]
    lu_r2 = lu_row['r2_score'].values[0] if len(lu_row) > 0 else None
    case_data.append((case_name, r2, lu_r2, idx))

# Sort by R2 descending
case_data.sort(key=lambda x: x[1], reverse=True)

print(f"Plotting {len(case_data)} cases...")

# 1. Individual 4-panel plots
for i, (case_name, r2, lu_r2, idx) in enumerate(case_data):
    x_input = X_np[idx, 0]
    gt = Y_np[idx, 0].copy()
    pr = pred_all[idx, 0].copy()
    mask = (~np.isnan(gt)) & (x_input <= 0)

    fig, axes = plt.subplots(1, 4, figsize=(20, 4.5))

    # Input
    ax = axes[0]
    im = ax.imshow(x_input, cmap='terrain', origin='lower')
    ax.set_title(f"{case_name}", fontsize=10)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # GT
    ax = axes[1]
    gt_disp = gt.copy(); gt_disp[~mask] = np.nan
    vmin = np.nanmin(gt_disp[mask]) if mask.sum() > 0 else 0
    vmax = np.nanmax(gt_disp[mask]) if mask.sum() > 0 else 1
    im = ax.imshow(gt_disp, cmap='RdYlBu_r', origin='lower', vmin=vmin, vmax=vmax)
    ax.set_title("Ground Truth", fontsize=10)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # Pred
    ax = axes[2]
    pr_disp = pr.copy(); pr_disp[~mask] = np.nan
    im = ax.imshow(pr_disp, cmap='RdYlBu_r', origin='lower', vmin=vmin, vmax=vmax)
    ax.set_title("Prediction", fontsize=10)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # Error
    ax = axes[3]
    error = pr - gt; error[~mask] = np.nan
    elim = np.nanmax(np.abs(error[mask])) if mask.sum() > 0 else 0.1
    im = ax.imshow(error, cmap='RdBu', origin='lower', vmin=-elim, vmax=elim)
    ax.set_title("Error", fontsize=10)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    lu_str = f"Lu={lu_r2:.3f}" if lu_r2 is not None else "Lu=N/A"
    fig.suptitle(f"#{i+1} {case_name}  |  Ours R2={r2:.3f}  |  {lu_str}", fontsize=11, fontweight='bold')
    plt.tight_layout()
    fig.savefig(str(OUT / f"{i+1:03d}_{case_name.replace('/','_')}.png"), dpi=100, bbox_inches='tight')
    plt.close(fig)

    if (i+1) % 20 == 0:
        print(f"  {i+1}/{len(case_data)} done")

# 2. Summary error grid: sorted by R2
n = len(case_data)
ncols = 10
nrows = (n + ncols - 1) // ncols

fig, axes = plt.subplots(nrows, ncols, figsize=(ncols*2.5, nrows*2.5))
axes_flat = axes.flatten()

for i, (case_name, r2, lu_r2, idx) in enumerate(case_data):
    ax = axes_flat[i]
    x_input = X_np[idx, 0]
    gt = Y_np[idx, 0]
    pr = pred_all[idx, 0]
    mask = (~np.isnan(gt)) & (x_input <= 0)
    error = pr - gt; error[~mask] = np.nan
    elim = np.nanmax(np.abs(error[mask])) if mask.sum() > 0 else 0.1
    im = ax.imshow(error, cmap='RdBu', origin='lower', vmin=-elim, vmax=elim)
    
    color = 'green' if r2 > 0.7 else ('orange' if r2 > 0.4 else 'red')
    ax.set_title(f"{case_name}\nR2={r2:.2f}", fontsize=5, color=color)
    ax.set_xticks([]); ax.set_yticks([])

# Hide empty
for i in range(len(case_data), len(axes_flat)):
    axes_flat[i].set_visible(False)

fig.suptitle("All test cases: Error maps sorted by R2 (best→worst)", fontsize=12, fontweight='bold')
plt.tight_layout()
fig.savefig(str(OUT / "all_cases_error_grid.png"), dpi=150, bbox_inches='tight')
plt.close(fig)
print("Saved: all_cases_error_grid.png")

# 3. GT vs Pred comparison grid (top 20 best + bottom 10 worst)
top20 = case_data[:20]
bot10 = case_data[-10:]
selection = top20 + bot10

fig, axes = plt.subplots(len(selection), 3, figsize=(12, len(selection)*1.8))
for i, (case_name, r2, lu_r2, idx) in enumerate(selection):
    x_input = X_np[idx, 0]
    gt = Y_np[idx, 0].copy()
    pr = pred_all[idx, 0].copy()
    mask = (~np.isnan(gt)) & (x_input <= 0)
    
    vmin = np.nanmin(gt[mask]) if mask.sum() > 0 else 0
    vmax = np.nanmax(gt[mask]) if mask.sum() > 0 else 1

    ax = axes[i, 0]
    ax.imshow(gt, cmap='RdYlBu_r', origin='lower', vmin=vmin, vmax=vmax)
    ax.set_ylabel(f"{case_name}\nR2={r2:.2f}", fontsize=6)
    ax.set_xticks([]); ax.set_yticks([])

    ax = axes[i, 1]
    ax.imshow(pr, cmap='RdYlBu_r', origin='lower', vmin=vmin, vmax=vmax)
    ax.set_xticks([]); ax.set_yticks([])

    ax = axes[i, 2]
    error = pr - gt; error[~mask] = np.nan
    elim = np.nanmax(np.abs(error[mask])) if mask.sum() > 0 else 0.1
    ax.imshow(error, cmap='RdBu', origin='lower', vmin=-elim, vmax=elim)
    ax.set_xticks([]); ax.set_yticks([])

axes[0, 0].set_title("GT", fontsize=10)
axes[0, 1].set_title("Pred", fontsize=10)
axes[0, 2].set_title("Error", fontsize=10)
fig.suptitle("Top 20 best + Bottom 10 worst: GT vs Pred vs Error", fontsize=12, fontweight='bold')
plt.tight_layout()
fig.savefig(str(OUT / "top_bot_comparison.png"), dpi=150, bbox_inches='tight')
plt.close(fig)
print("Saved: top_bot_comparison.png")

print(f"\nDone! {len(case_data)} individual plots + 2 summary figures")
