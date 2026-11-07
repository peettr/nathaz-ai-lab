"""
Plot spatial wind field predictions: input topo, ground truth, prediction, error.
"""
import sys, os, numpy as np, torch, re
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
lu_df['case_name'] = lu_df['topo'].astype(str) + '_d' + lu_df['angle'].astype(str)
print(f"Lu columns: {lu_df.columns.tolist()}")

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

# Run inference
with torch.no_grad():
    pred_all = model(X_test).cpu().numpy()

X_np = X_test.cpu().numpy()
Y_np = Y_test.cpu().numpy()

# Pick interesting cases
pick_cases = [
    "US35_d45",        # idealized, high R2
    "AU-Syd-U4_d90",   # realistic, we beat Lu
    "KO-SE-V8_d90",    # realistic, we beat Lu significantly
    "AU-MEL-V2_d90",   # realistic, we beat Lu
    "VA25-CL-28_d00",  # idealized, we beat Lu
    "US64_d00",        # idealized, Lu beats us
    "Val-AU-Mel-U2_d00",  # worst case
    "AU-SYD-V1_d00",   # realistic, hard case
]

OUT = ROOT / "results" / "wind_field_plots"
OUT.mkdir(exist_ok=True)

grouped = test_df.groupby('case_name')

for case_name in pick_cases:
    if case_name not in grouped.groups:
        print(f"Skip {case_name} (not in test set)")
        continue

    group = grouped.get_group(case_name)
    indices = group.index.tolist()

    # Get Lu R2
    lu_row = lu_df[lu_df['case_name'] == case_name]
    lu_r2 = lu_row['r2_score'].values[0] if len(lu_row) > 0 else None

    # Use first patch
    idx = indices[0]
    x_input = X_np[idx, 0]
    all_true = Y_np[idx, 0]
    all_pred = pred_all[idx, 0]
    mask = (~np.isnan(all_true)) & (x_input <= 0)

    # Build figure
    fig, axes = plt.subplots(1, 4, figsize=(22, 5))

    # 1. Input topography
    ax = axes[0]
    im = ax.imshow(x_input, cmap='terrain', origin='lower')
    ax.set_title(f"Input: {case_name}", fontsize=12)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # 2. Ground truth
    ax = axes[1]
    gt = all_true.copy(); gt[~mask] = np.nan
    vmin = np.nanmin(gt[mask]) if mask.sum() > 0 else 0
    vmax = np.nanmax(gt[mask]) if mask.sum() > 0 else 1
    im = ax.imshow(gt, cmap='RdYlBu_r', origin='lower', vmin=vmin, vmax=vmax)
    ax.set_title("Ground Truth (norm.)", fontsize=12)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # 3. Prediction
    ax = axes[2]
    pr = all_pred.copy(); pr[~mask] = np.nan
    im = ax.imshow(pr, cmap='RdYlBu_r', origin='lower', vmin=vmin, vmax=vmax)
    ax.set_title("Prediction (norm.)", fontsize=12)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # 4. Error map
    ax = axes[3]
    error = all_pred - all_true
    error[~mask] = np.nan
    elim = np.nanmax(np.abs(error[mask])) if mask.sum() > 0 else 0.1
    im = ax.imshow(error, cmap='RdBu', origin='lower', vmin=-elim, vmax=elim)
    ax.set_title("Error (pred - true)", fontsize=12)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # R2
    if mask.sum() > 0:
        p = all_pred[mask]; t = all_true[mask]
        ss_res = np.sum((p - t)**2)
        ss_tot = np.sum((t - t.mean())**2)
        r2 = 1 - ss_res/ss_tot if ss_tot > 0 else -999
    else:
        r2 = -999

    lu_str = f"Lu R2={lu_r2:.3f}" if lu_r2 is not None else "Lu R2=N/A"
    fig.suptitle(f"{case_name}  |  Ours R2={r2:.3f}  |  {lu_str}", fontsize=14, fontweight='bold')
    plt.tight_layout()

    fname = case_name.replace('/', '_') + '.png'
    fig.savefig(str(OUT / fname), dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {fname}  R2={r2:.3f}  {lu_str}")

# Also make a summary figure: 2x4 grid
fig, axes = plt.subplots(2, 4, figsize=(22, 10))
axes_flat = axes.flatten()
for i, case_name in enumerate(pick_cases):
    if case_name not in grouped.groups:
        continue
    group = grouped.get_group(case_name)
    idx = group.index[0]
    x_input = X_np[idx, 0]
    gt = Y_np[idx, 0].copy()
    pr = pred_all[idx, 0].copy()
    mask = (~np.isnan(gt)) & (x_input <= 0)

    ax = axes_flat[i]
    error = pr - gt
    error[~mask] = np.nan
    elim = np.nanmax(np.abs(error[mask])) if mask.sum() > 0 else 0.1
    ax.imshow(error, cmap='RdBu', origin='lower', vmin=-elim, vmax=elim)

    p = pr[mask]; t = gt[mask]
    if mask.sum() > 0:
        ss_res = np.sum((p-t)**2); ss_tot = np.sum((t-t.mean())**2)
        r2 = 1-ss_res/ss_tot if ss_tot>0 else -999
    else:
        r2 = -999
    ax.set_title(f"{case_name}\nR2={r2:.3f}", fontsize=9)
    ax.set_xticks([]); ax.set_yticks([])

fig.suptitle("Error Maps (pred - true) for selected cases", fontsize=14, fontweight='bold')
plt.tight_layout()
fig.savefig(str(OUT / "summary_error_maps.png"), dpi=150, bbox_inches='tight')
plt.close(fig)
print("Saved: summary_error_maps.png")

print("\nDone!")
