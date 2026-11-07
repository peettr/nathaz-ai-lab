#!/usr/bin/env python3
"""Fig 7 v3: Match Lu et al. Figure 7 layout style.
Each case: LES wind field (top) + U-net prediction (bottom) + PDF histogram (right)
Buildings = very light gray, PDF excludes buildings."""
import os, sys, re, json, numpy as np, torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import xarray as xr
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

# 6 representative cases
selected_cases = [
    ('VA4444-CL-28_d45', 'Variable height, dense, 45 deg'),
    ('VA25-SM-28_d00', 'Variable height, sparse, 0 deg'),
    ('US-New-V1_d90', 'Realistic, US, 90 deg'),
    ('AU-MEL-V2_d90', 'Realistic, AU Melbourne, 90 deg'),
    ('KO-SE-V8_d90', 'Realistic, KO Seoul, 90 deg'),
    ('VA64-SM-28_d00', 'Variable height, very sparse, 0 deg'),
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
print("Model loaded, predictions done")

def predict_case(cn):
    case_dir = RAW_DIR / cn
    if not case_dir.is_dir():
        return None
    topo = np.flipud(np.loadtxt(str(case_dir / (cn + '_topo')), dtype=np.float32))
    with xr.open_dataset(str(case_dir / (cn + '_ped.nc'))) as ds:
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
    bld_mask = topo > 0
    valid = (~bld_mask) & np.isfinite(truth) & np.isfinite(pred)
    t = truth[valid]; p = pred[valid]
    ss_res = np.sum((t-p)**2); ss_tot = np.sum((t-t.mean())**2)
    r2 = 1 - ss_res/ss_tot if ss_tot > 0 else -999
    # For display: wind = actual, buildings = NaN
    truth_disp = np.where(bld_mask, np.nan, truth)
    pred_disp = np.where(bld_mask, np.nan, pred)
    # Building overlay: normalized height
    bld_height = np.where(bld_mask, topo, 0).astype(float)
    bld_max = bld_height.max() if bld_height.max() > 0 else 1
    bld_norm = bld_height / bld_max
    return truth_disp, pred_disp, bld_norm, bld_mask, r2

# === Lu-style layout: 3 pairs (a,b,c), each pair = 2 cases side by side ===
# Each case: LES (top) + UNet (bottom) stacked vertically, PDF to the right
fig = plt.figure(figsize=(22, 18))

# Outer: 3 rows (pairs) x 2 cols (cases per pair)
outer = gridspec.GridSpec(3, 2, figure=fig, hspace=0.35, wspace=0.2,
                          left=0.05, right=0.92, top=0.93, bottom=0.03)

case_idx = 0
for row in range(3):
    for col in range(2):
        if case_idx >= len(selected_cases):
            break
        cn, desc = selected_cases[case_idx]
        result = predict_case(cn)
        if result is None:
            case_idx += 1
            continue
        truth_disp, pred_disp, bld_norm, bld_mask, r2 = result
        
        # Inner: 2 rows (LES, UNet) x 2 cols (spatial, PDF)
        inner = gridspec.GridSpecFromSubplotSpec(2, 2, subplot_spec=outer[row, col],
                                                  width_ratios=[1.2, 0.5],
                                                  height_ratios=[1, 1],
                                                  hspace=0.08, wspace=0.15)
        ax_les = fig.add_subplot(inner[0, 0])
        ax_unet = fig.add_subplot(inner[1, 0])
        ax_pdf = fig.add_subplot(inner[:, 1])  # PDF spans both rows
        
        vmin = np.nanmin([np.nanmin(truth_disp), np.nanmin(pred_disp)])
        vmax = np.nanmax([np.nanmax(truth_disp), np.nanmax(pred_disp)])
        
        # LES wind field
        im1 = ax_les.imshow(truth_disp, origin='lower', cmap='jet', vmin=vmin, vmax=vmax, aspect='equal')
        # Buildings as very light gray overlay
        bld_rgba = np.zeros((*bld_norm.shape, 4))
        mask = bld_norm > 0
        gray = 1.0 - 0.6 * bld_norm  # short=1.0(white), tall=0.40(dark gray)
        bld_rgba[mask, 0] = gray[mask]
        bld_rgba[mask, 1] = gray[mask]
        bld_rgba[mask, 2] = gray[mask]
        bld_rgba[mask, 3] = 0.7  # more opaque for visibility
        ax_les.imshow(bld_rgba, origin='lower', aspect='equal')
        ax_les.set_title('LES', fontsize=9, fontweight='bold', loc='left')
        ax_les.set_xticks([]); ax_les.set_yticks([])
        
        # UNet prediction
        im2 = ax_unet.imshow(pred_disp, origin='lower', cmap='jet', vmin=vmin, vmax=vmax, aspect='equal')
        ax_unet.imshow(bld_rgba, origin='lower', aspect='equal')
        ax_unet.set_title('U-net', fontsize=9, fontweight='bold', loc='left')
        ax_unet.set_xlabel('x (m)', fontsize=7)
        ax_unet.set_ylabel('y (m)', fontsize=7)
        ax_unet.tick_params(labelsize=6)
        
        # Shared colorbar for both
        cb = plt.colorbar(im1, ax=[ax_les, ax_unet], fraction=0.03, pad=0.02)
        cb.set_label('Wind speed (m/s)', fontsize=7)
        cb.ax.tick_params(labelsize=6)
        
        # PDF histogram (non-building pixels only)
        t_flat = truth_disp[np.isfinite(truth_disp)].flatten()
        p_flat = pred_disp[np.isfinite(pred_disp)].flatten()
        bins = np.linspace(0, max(t_flat.max(), p_flat.max(), 0.1), 30)
        ax_pdf.hist(t_flat, bins=bins, density=True, alpha=0.6, color='#2196F3', label='LES')
        ax_pdf.hist(p_flat, bins=bins, density=True, alpha=0.6, color='#FF9800', label='U-net')
        r2_color = '#4CAF50' if r2 > 0.5 else '#F44336'
        ax_pdf.set_title('R\u00b2 = %.2f' % r2, fontsize=11, fontweight='bold', color=r2_color)
        ax_pdf.set_xlabel('Wind speed\n(m/s)', fontsize=7)
        ax_pdf.set_ylabel('Probability\ndensity', fontsize=7)
        ax_pdf.tick_params(labelsize=6)
        ax_pdf.legend(fontsize=7, loc='upper right')
        
        # Case label
        pair_letter = chr(ord('a') + row)
        fig.text(outer[row, col].get_position(fig).x0 - 0.02,
                 outer[row, col].get_position(fig).y1 + 0.01,
                 '(%c%d) %s' % (pair_letter, col+1, cn),
                 fontsize=9, fontweight='bold', va='bottom',
                 bbox=dict(boxstyle='round,pad=0.2', facecolor='#FFF9C4', alpha=0.8))
        
        case_idx += 1

# Add shared building height grayscale colorbar
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.cm import ScalarMappable
import matplotlib.colors as mcolors
ax_cb = fig.add_axes([0.93, 0.15, 0.015, 0.25])  # [left, bottom, width, height]
gray_cmap = LinearSegmentedColormap.from_list('bld_height', ['#FFFFFF', '#666666'])
norm = mcolors.Normalize(vmin=0, vmax=None)  # relative height 0-1
sm = ScalarMappable(cmap=gray_cmap, norm=mcolors.Normalize(0, 1))
sm.set_array([])
cb_bld = fig.colorbar(sm, cax=ax_cb)
cb_bld.set_label('Building height\n(normalized)', fontsize=7)
cb_bld.set_ticks([0, 0.5, 1.0])
cb_bld.set_ticklabels(['Low', 'Mid', 'High'])
cb_bld.ax.tick_params(labelsize=6)

fig.suptitle('Wind Field Comparison: LES vs U-net Prediction\n'
             'Buildings shown in light gray | PDF computed on non-building pixels only',
             fontsize=14, fontweight='bold', y=0.97)
plt.savefig(str(ROOT / 'results/fig7_v3.png'), dpi=150, bbox_inches='tight', facecolor='white')
print('Saved fig7_v3.png')
