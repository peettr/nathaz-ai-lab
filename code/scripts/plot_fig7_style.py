#!/usr/bin/env python3
"""Generate Fig 7 style: wind field comparison + histogram for 6 representative cases.
Uses seed 1 model, runs on CRC GPU."""
import os, sys, re, json, numpy as np, torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd, xarray as xr
from pathlib import Path
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path('/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset')
RAW_DIR = Path('/groups/kareem/[用户]/graph-deeponet-wind/data/urbantales/raw')

sys.path.insert(0, str(ROOT / 'scripts' / 'models'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'references'))
from unet_lu_7level import UNetLu7Level
from data_formatter_fixed import DataFormatterFixed as DataFormatter

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Device: %s, GPU: %s" % (device, torch.cuda.get_device_name(device)))

# Load all patches
train_pt = torch.load(ROOT / 'data/full_masked_640/train.pt', map_location='cpu', weights_only=False)
test_pt = torch.load(ROOT / 'data/full_masked_640/test.pt', map_location='cpu', weights_only=False)
X_all = torch.cat([train_pt["X"], test_pt["X"]], dim=0)

train_cn = train_pt["case_names"]
test_cn = test_pt["case_names"]
train_p2c = train_pt["patch_to_case"]
test_p2c = test_pt["patch_to_case"]

patch_case_names = []
for i in range(len(train_p2c)):
    patch_case_names.append(train_cn[int(train_p2c[i])])
for i in range(len(test_p2c)):
    patch_case_names.append(test_cn[int(test_p2c[i])])

case_to_patches = {}
for idx, cn in enumerate(patch_case_names):
    if cn not in case_to_patches:
        case_to_patches[cn] = []
    case_to_patches[cn].append(idx)

del train_pt, test_pt

# Select 6 representative cases
# 2 idealized (1 good + 1 bad), 2 realistic (1 good + 1 bad), 2 interesting
selected_cases = [
    'VA4444-CL-28_d45',    # idealized, dense, d45 - usually good
    'VA25-SM-28_d00',      # idealized, sparse, d00 - often bad
    'US-New-V1_d90',       # realistic, large domain
    'AU-MEL-V2_d90',       # realistic
    'KO-SE-V8_d90',        # realistic, interesting
    'VA64-SM-28_d00',      # idealized, very sparse - worst case
]

# Load model (seed 1)
model_path = ROOT / 'results/full_masked_640_7level/seed_1/model_best.pt'
model = UNetLu7Level(n_c=16).to(device)
model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
model.eval()

loader = DataLoader(TensorDataset(X_all.to(device)), batch_size=16, shuffle=False)
all_pred = []
with torch.no_grad():
    for (x,) in loader:
        all_pred.append(model(x))
pred_all = np.nan_to_num(
    torch.cat(all_pred, dim=0).cpu().numpy()[:, 0, :, :],
    nan=0.0).astype(np.float32)
del model
torch.cuda.empty_cache()

# For each case, predict and restore
def predict_case(cn):
    case_dir = RAW_DIR / cn
    if not case_dir.is_dir():
        return None, None, None
    topo_file = str(case_dir / ("%s_topo" % cn))
    ped_file = str(case_dir / ("%s_ped.nc" % cn))
    topo = np.flipud(np.loadtxt(topo_file, dtype=np.float32))
    with xr.open_dataset(ped_file) as ds:
        Uped = ds["Uped"].values.astype(np.float32)
    combined = Uped.copy()
    combined[topo > 0] = -topo[topo > 0]
    m = re.search(r"_d(\d+)$", cn)
    angle = int(m.group(1))
    
    patch_indices = case_to_patches.get(cn, [])
    if len(patch_indices) == 0:
        return None, None, None
    
    formatter = DataFormatter(raw_data=[combined], wind_angles=[angle], formatted_shape=640)
    pred_patches = np.stack([pred_all[i] for i in patch_indices], axis=0)
    pred_input = pred_patches[:, np.newaxis, :, :]
    restored = formatter.restore_raw_output_data(pred_input)
    pred_raw = np.nanmean(restored, axis=0)
    
    if combined.shape != pred_raw.shape:
        if combined.shape == pred_raw.T.shape:
            pred_raw = pred_raw.T
        else:
            return None, None, None
    
    truth = combined.copy()
    pred = pred_raw.copy()
    
    # Compute R2
    valid = (truth >= 0) & np.isfinite(truth) & np.isfinite(pred)
    t = truth[valid]
    p = pred[valid]
    ss_res = np.sum((t-p)**2)
    ss_tot = np.sum((t-t.mean())**2)
    r2 = 1 - ss_res/ss_tot if ss_tot > 0 else -999
    
    # Mask buildings for display
    display_truth = np.where(truth >= 0, truth, np.nan)
    display_pred = np.where(pred >= 0, pred, np.nan)
    
    return display_truth, display_pred, r2

# Plot 3 pairs (a, b, c), each pair = 2 cases
fig, axes = plt.subplots(3, 2, figsize=(14, 18),
                          gridspec_kw={'width_ratios': [1, 1]})

for row in range(3):
    for col in range(2):
        case_idx = row * 2 + col
        if case_idx >= len(selected_cases):
            continue
        cn = selected_cases[case_idx]
        ax = axes[row, col]
        
        truth, pred, r2 = predict_case(cn)
        if truth is None:
            ax.text(0.5, 0.5, '%s\nData not found' % cn, ha='center', va='center',
                    transform=ax.transAxes, fontsize=10)
            continue
        
        # Create inner grid: 2 spatial maps + 1 histogram
        inner = ax.get_subplotspec()
        ax.set_visible(False)
        
        gs = inner.subgridspec(1, 3, width_ratios=[1, 1, 0.8], wspace=0.3)
        ax_les = fig.add_subplot(gs[0])
        ax_pred = fig.add_subplot(gs[1])
        ax_hist = fig.add_subplot(gs[2])
        
        vmin = np.nanmin([np.nanmin(truth), np.nanmin(pred)])
        vmax = np.nanmax([np.nanmax(truth), np.nanmax(pred)])
        
        im1 = ax_les.imshow(truth, origin='lower', cmap='jet', vmin=vmin, vmax=vmax, aspect='equal')
        ax_les.set_title('LES', fontsize=9)
        ax_les.set_xlabel('x', fontsize=8)
        ax_les.set_ylabel('y', fontsize=8)
        ax_les.tick_params(labelsize=6)
        
        im2 = ax_pred.imshow(pred, origin='lower', cmap='jet', vmin=vmin, vmax=vmax, aspect='equal')
        ax_pred.set_title('U-net', fontsize=9)
        ax_pred.set_xlabel('x', fontsize=8)
        ax_pred.tick_params(labelsize=6)
        
        # Colorbar
        cb = plt.colorbar(im2, ax=[ax_les, ax_pred], fraction=0.04, pad=0.02)
        cb.set_label('Wind speed (m/s)', fontsize=7)
        cb.ax.tick_params(labelsize=6)
        
        # Histogram
        t_flat = truth[np.isfinite(truth)].flatten()
        p_flat = pred[np.isfinite(pred)].flatten()
        bins = np.linspace(0, max(t_flat.max(), p_flat.max()), 40)
        ax_hist.hist(t_flat, bins=bins, density=True, alpha=0.6, color='#2196F3', label='LES')
        ax_hist.hist(p_flat, bins=bins, density=True, alpha=0.6, color='#FF9800', label='U-net')
        ax_hist.set_title('R\u00b2 = %.2f' % r2, fontsize=10, fontweight='bold',
                         color='#4CAF50' if r2 > 0.5 else '#F44336')
        ax_hist.set_xlabel('Wind speed (m/s)', fontsize=7)
        ax_hist.set_ylabel('Density', fontsize=7)
        ax_hist.tick_params(labelsize=6)
        ax_hist.legend(fontsize=7)
        
        # Case label
        fig.text(0.02 if col==0 else 0.52,
                 0.97 - row * 0.333,
                 '(%c) %s' % (chr(ord('a')+row), cn),
                 fontsize=10, fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFF9C4', alpha=0.8))

fig.suptitle('Wind Field Comparison: LES vs U-net Prediction (Lu et al. Fig 7 style)\n'
             'Seed 1 model | 6 representative cases',
             fontsize=13, fontweight='bold', y=0.99)
plt.savefig(str(ROOT / 'results/fig7_style.png'), dpi=150, bbox_inches='tight', facecolor='white')
print('Saved fig7_style.png')
