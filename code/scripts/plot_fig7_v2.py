#!/usr/bin/env python3
"""Fig 7: wind field comparison + histogram. Buildings = light gray, PDF excludes buildings."""
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

# Load patches
train_pt = torch.load(ROOT / 'data/full_masked_640/train.pt', map_location='cpu', weights_only=False)
test_pt = torch.load(ROOT / 'data/full_masked_640/test.pt', map_location='cpu', weights_only=False)
X_all = torch.cat([train_pt["X"], test_pt["X"]], dim=0)

train_cn = train_pt["case_names"]; test_cn = test_pt["case_names"]
train_p2c = train_pt["patch_to_case"]; test_p2c = test_pt["patch_to_case"]

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
selected_cases = [
    ('VA4444-CL-28_d45', 'Idealized, dense, d=45'),
    ('VA25-SM-28_d00', 'Idealized, sparse, d=0'),
    ('US-New-V1_d90', 'Realistic, US'),
    ('AU-MEL-V2_d90', 'Realistic, AU'),
    ('KO-SE-V8_d90', 'Realistic, KO'),
    ('VA64-SM-28_d00', 'Idealized, very sparse, d=0'),
]

# Load model (seed 1)
model = UNetLu7Level(n_c=16).to(device)
model.load_state_dict(torch.load(ROOT / 'results/full_masked_640_7level/seed_1/model_best.pt',
                                  map_location=device, weights_only=True))
model.eval()
loader = DataLoader(TensorDataset(X_all.to(device)), batch_size=16, shuffle=False)
all_pred = []
with torch.no_grad():
    for (x,) in loader:
        all_pred.append(model(x))
pred_all = np.nan_to_num(torch.cat(all_pred, dim=0).cpu().numpy()[:, 0, :, :],
                          nan=0.0).astype(np.float32)
del model; torch.cuda.empty_cache()

def predict_case(cn):
    case_dir = RAW_DIR / cn
    if not case_dir.is_dir():
        return None
    topo_file = str(case_dir / (cn + '_topo'))
    ped_file = str(case_dir / (cn + '_ped.nc'))
    topo = np.flipud(np.loadtxt(topo_file, dtype=np.float32))
    with xr.open_dataset(ped_file) as ds:
        Uped = ds["Uped"].values.astype(np.float32)
    combined = Uped.copy()
    combined[topo > 0] = -topo[topo > 0]
    m = re.search(r"_d(\d+)$", cn)
    angle = int(m.group(1))
    
    patch_indices = case_to_patches.get(cn, [])
    if len(patch_indices) == 0:
        return None
    formatter = DataFormatter(raw_data=[combined], wind_angles=[angle], formatted_shape=640)
    pred_patches = np.stack([pred_all[i] for i in patch_indices], axis=0)
    pred_input = pred_patches[:, np.newaxis, :, :]
    restored = formatter.restore_raw_output_data(pred_input)
    pred_raw = np.nanmean(restored, axis=0)
    
    if combined.shape != pred_raw.shape:
        if combined.shape == pred_raw.T.shape:
            pred_raw = pred_raw.T
        else:
            return None
    
    truth = combined.copy()
    pred = pred_raw.copy()
    
    # Building mask
    bld_mask = topo > 0
    
    # R2 on non-building pixels
    valid = (~bld_mask) & np.isfinite(truth) & np.isfinite(pred)
    t = truth[valid]; p = pred[valid]
    ss_res = np.sum((t-p)**2); ss_tot = np.sum((t-t.mean())**2)
    r2 = 1 - ss_res/ss_tot if ss_tot > 0 else -999
    
    # For display: wind speed with buildings as NaN
    truth_disp = np.where(bld_mask, np.nan, truth)
    pred_disp = np.where(bld_mask, np.nan, pred)
    
    # Building height map (normalized for display)
    bld_height = np.where(bld_mask, topo, 0)
    bld_max = bld_height.max() if bld_height.max() > 0 else 1
    bld_norm = bld_height / bld_max  # 0-1 for buildings
    
    return truth_disp, pred_disp, bld_norm, r2

# === Plot: 3 rows x 2 cols, each case = LES + UNet + PDF ===
fig = plt.figure(figsize=(16, 20))
gs = fig.add_gridspec(3, 2, hspace=0.35, wspace=0.25)

for idx, (cn, desc) in enumerate(selected_cases):
    row = idx // 2
    col = idx % 2
    
    result = predict_case(cn)
    if result is None:
        continue
    truth_disp, pred_disp, bld_norm, r2 = result
    
    # Inner grid: 2 spatial + 1 histogram
    inner = gs[row, col].subgridspec(1, 3, width_ratios=[1, 1, 0.7], wspace=0.15)
    ax_les = fig.add_subplot(inner[0])
    ax_pred = fig.add_subplot(inner[1])
    ax_hist = fig.add_subplot(inner[2])
    
    # Wind speed range (excluding NaN)
    vmin = np.nanmin([np.nanmin(truth_disp), np.nanmin(pred_disp)])
    vmax = np.nanmax([np.nanmax(truth_disp), np.nanmax(pred_disp)])
    
    # Custom colormap with very light gray for buildings
    from matplotlib.colors import ListedColormap
    import matplotlib.cm as cm
    
    jet = cm.get_cmap('jet')
    
    # LES plot
    im1 = ax_les.imshow(truth_disp, origin='lower', cmap='jet', vmin=vmin, vmax=vmax, aspect='equal')
    # Overlay buildings as very light gray (0.92 = very light)
    bld_display = np.where(bld_norm > 0, 0.92, np.nan)
    ax_les.imshow(bld_display, origin='lower', cmap='gray', vmin=0, vmax=1, aspect='equal', alpha=0.85)
    ax_les.set_title('LES', fontsize=10, fontweight='bold')
    ax_les.tick_params(labelsize=6)
    
    # UNet plot
    im2 = ax_pred.imshow(pred_disp, origin='lower', cmap='jet', vmin=vmin, vmax=vmax, aspect='equal')
    ax_pred.imshow(bld_display, origin='lower', cmap='gray', vmin=0, vmax=1, aspect='equal', alpha=0.85)
    ax_pred.set_title('U-net', fontsize=10, fontweight='bold')
    ax_pred.tick_params(labelsize=6)
    
    # Shared colorbar
    cb = plt.colorbar(im1, ax=[ax_les, ax_pred], fraction=0.03, pad=0.02)
    cb.set_label('m/s', fontsize=7)
    cb.ax.tick_params(labelsize=6)
    
    # PDF histogram: exclude building pixels (already NaN in truth_disp/pred_disp)
    t_flat = truth_disp[np.isfinite(truth_disp)].flatten()
    p_flat = pred_disp[np.isfinite(pred_disp)].flatten()
    bins = np.linspace(0, max(t_flat.max(), p_flat.max()), 35)
    ax_hist.hist(t_flat, bins=bins, density=True, alpha=0.6, color='#2196F3', label='LES')
    ax_hist.hist(p_flat, bins=bins, density=True, alpha=0.6, color='#FF9800', label='U-net')
    
    r2_color = '#4CAF50' if r2 > 0.5 else '#F44336'
    ax_hist.set_title('R\u00b2 = %.2f' % r2, fontsize=11, fontweight='bold', color=r2_color)
    ax_hist.set_xlabel('Wind speed (m/s)', fontsize=7)
    ax_hist.set_ylabel('Density', fontsize=7)
    ax_hist.tick_params(labelsize=6)
    ax_hist.legend(fontsize=7, loc='upper right')
    
    # Case label
    label = '(%c) %s\n%s' % (chr(ord('a')+idx), cn, desc)
    fig.text(ax_les.get_position().x0 - 0.01, 
             ax_les.get_position().y1 + 0.01,
             label, fontsize=9, fontweight='bold', va='bottom')

fig.suptitle('Wind Field Comparison: LES vs U-net Prediction\n'
             'Buildings shown in light gray | PDF computed on non-building pixels',
             fontsize=14, fontweight='bold', y=0.98)
plt.savefig(str(ROOT / 'results/fig7_v2.png'), dpi=150, bbox_inches='tight', facecolor='white')
print('Saved fig7_v2.png')
