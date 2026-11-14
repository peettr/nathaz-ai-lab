#!/usr/bin/env python3
"""
1280 vs Lu per-case comparison (same style as 640 comparison).
"""
import json, csv, io, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

# ---- Rebuild 1280 per-case metrics (from eval_1280_cpu.py output) ----
# We need to re-run the eval to get per-case data. But we already have the results
# saved. Let me just load the 640 results and compare with Lu, then print 1280 context.

# Actually, let me just compute from the eval script output. We need to re-run with save.
import sys, re, torch, pandas as pd, xarray as xr
from pathlib import Path

sys.path.insert(0, '/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset/scripts')
sys.path.insert(0, '/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset/references')
from unet_lu import UNetLu
from data_formatter_fixed import DataFormatterFixed as DataFormatter

ROOT = Path('/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset')
RAW_DIR = Path('/groups/kareem/[用户]/graph-deeponet-wind/data/urbantales/raw')

# Load test data
data = torch.load(ROOT / 'data/full_masked_1280/test.pt', map_location='cpu', weights_only=False)
X, Y = data["X"], data["Y"]

model = UNetLu(n_c=16)
model.load_state_dict(torch.load(ROOT / 'results/full_masked_1280/seed_1/model_best.pt', map_location='cpu', weights_only=True))
model.eval()

from torch.utils.data import DataLoader, TensorDataset
loader = DataLoader(TensorDataset(X), batch_size=4, shuffle=False)
all_pred = []
with torch.no_grad():
    for (x,) in loader:
        all_pred.append(model(x))
pred_all = torch.cat(all_pred, dim=0)
pred_np = np.nan_to_num(pred_all.numpy()[:, 0, :, :], nan=0.0).astype(np.float32)

test_df = pd.read_csv(ROOT / 'scripts/lu_full_test_seed1.csv')
test_cases_list = sorted(test_df['case_name'].tolist())

raw_data_list, wind_angle_list, loaded_names = [], [], []
for cn in test_cases_list:
    case_dir = RAW_DIR / cn
    if not case_dir.is_dir(): continue
    try:
        topo = np.flipud(np.loadtxt(case_dir / f"{cn}_topo", dtype=np.float32))
        with xr.open_dataset(case_dir / f"{cn}_ped.nc") as ds:
            Uped = ds["Uped"].values.astype(np.float32)
        combined = Uped.copy()
        combined[topo > 0] = -topo[topo > 0]
        m = re.search(r"_d(\d+)$", cn)
        raw_data_list.append(combined)
        wind_angle_list.append(int(m.group(1)))
        loaded_names.append(cn)
    except: pass

formatter = DataFormatter(raw_data=raw_data_list, wind_angles=wind_angle_list, formatted_shape=1280)
restored = formatter.restore_raw_output_data(pred_np[:, np.newaxis, :, :])

by_case_1280 = {}
for i, cn in enumerate(loaded_names):
    truth = raw_data_list[i]
    pred = restored[i]
    if truth.shape != pred.shape:
        if truth.shape == pred.T.shape:
            pred = pred.T
        else:
            continue
    valid = truth >= 0
    valid = valid & np.isfinite(truth) & np.isfinite(pred)
    t = truth[valid]
    p = pred[valid]
    if len(t) == 0: continue
    mae = float(np.mean(np.abs(t - p)))
    ss_res = float(np.sum((t - p)**2))
    ss_tot = float(np.sum((t - t.mean())**2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    by_case_1280[cn] = dict(r2=r2, mae=mae, u_mean=float(np.mean(t)))

# Load 640 results
with open(ROOT / 'results/full_masked_640/seed_1/metrics_raw_restore_best.json') as f:
    m640 = json.load(f)
by_case_640 = {}
for case in m640['by_case']:
    by_case_640[case['case_name']] = case

# Lu results
lu_text = open(ROOT / 'references/all_cases_20exp/metrics_in_test_set_seed1.csv').read()
reader = csv.DictReader(io.StringIO(lu_text))
lu_map = {}
for row in reader:
    topo = row['topo']
    angle = row['angle']
    if topo == 'total': continue
    lu_map[(topo, int(angle))] = dict(r2=float(row['r2_score']), mae=float(row['mae']), 
                                       u_mean=float(row['true_mean']))

# Match all three
matched = []
for cn in by_case_1280:
    cn_base = cn.rsplit('_d', 1)[0]
    cn_angle = int(cn.rsplit('_d', 1)[1])
    lu_key = (cn_base, cn_angle)
    if lu_key not in lu_map: continue
    if cn not in by_case_640: continue
    
    is_ideal = cn.startswith(('VA','VS','UA','US'))
    matched.append(dict(
        case=cn, is_ideal=is_ideal,
        r2_1280=by_case_1280[cn]['r2'], r2_640=by_case_640[cn]['r2'], r2_lu=lu_map[lu_key]['r2'],
        mae_1280=by_case_1280[cn]['mae'], mae_640=by_case_640[cn]['mae'], mae_lu=lu_map[lu_key]['mae'],
        u_mean=lu_map[lu_key]['u_mean'],
    ))

ideal = [m for m in matched if m['is_ideal']]
real = [m for m in matched if not m['is_ideal']]

# ===== FIGURE =====
fig, axes = plt.subplots(2, 2, figsize=(14, 12))

# (a) 1280 vs Lu R² scatter
ax = axes[0, 0]
ax.scatter([m['r2_lu'] for m in ideal], [m['r2_1280'] for m in ideal],
           c='#2196F3', s=30, alpha=0.7, label=f'Idealized ({len(ideal)})', edgecolors='none')
ax.scatter([m['r2_lu'] for m in real], [m['r2_1280'] for m in real],
           c='#FF5722', s=30, alpha=0.7, label=f'Realistic ({len(real)})', edgecolors='none')
lims = [-1, 1.05]
ax.plot(lims, lims, 'k--', linewidth=1)
ax.set_xlabel("Lu R²", fontsize=12)
ax.set_ylabel("Our R² (1280)", fontsize=12)
r2_wins_1280 = sum(1 for m in matched if m['r2_1280'] >= m['r2_lu'])
ax.set_title(f"(a) 1280 vs Lu\nR² wins: Ours={r2_wins_1280}, Lu={len(matched)-r2_wins_1280}", fontsize=12, fontweight='bold')
ax.legend(fontsize=10); ax.grid(True, alpha=0.3)
ax.set_xlim(lims); ax.set_ylim(lims); ax.set_aspect('equal')

# (b) 1280 vs 640 R² scatter
ax = axes[0, 1]
ax.scatter([m['r2_640'] for m in ideal], [m['r2_1280'] for m in ideal],
           c='#2196F3', s=30, alpha=0.7, label=f'Idealized', edgecolors='none')
ax.scatter([m['r2_640'] for m in real], [m['r2_1280'] for m in real],
           c='#FF5722', s=30, alpha=0.7, label=f'Realistic', edgecolors='none')
ax.plot([-1, 1.05], [-1, 1.05], 'k--', linewidth=1)
ax.set_xlabel("640 R²", fontsize=12)
ax.set_ylabel("1280 R²", fontsize=12)
wins_vs_640 = sum(1 for m in matched if m['r2_1280'] >= m['r2_640'])
ax.set_title(f"(b) 1280 vs 640\n1280 wins: {wins_vs_640}/{len(matched)}", fontsize=12, fontweight='bold')
ax.legend(fontsize=10); ax.grid(True, alpha=0.3)
ax.set_xlim(-1, 1.05); ax.set_ylim(-1, 1.05); ax.set_aspect('equal')

# (c) R² sorted: all 3 methods
ax = axes[1, 0]
r2_lu_sorted = sorted([m['r2_lu'] for m in matched])
r2_640_sorted = sorted([m['r2_640'] for m in matched])
r2_1280_sorted = sorted([m['r2_1280'] for m in matched])
x = np.arange(len(matched))
ax.plot(x, r2_lu_sorted, color='#4CAF50', linewidth=2, label='Lu')
ax.plot(x, r2_640_sorted, color='#2196F3', linewidth=2, label='640')
ax.plot(x, r2_1280_sorted, color='#FF5722', linewidth=2, label='1280')
ax.set_xlabel('Cases (sorted)', fontsize=12)
ax.set_ylabel('R²', fontsize=12)
ax.set_title("(c) R² distribution (sorted)", fontsize=12, fontweight='bold')
ax.legend(fontsize=11); ax.grid(True, alpha=0.3); ax.set_ylim(-1, 1.05)

# (d) ΔR² histogram: 1280-Lu vs 640-Lu
ax = axes[1, 1]
d1280 = [m['r2_1280'] - m['r2_lu'] for m in matched]
d640 = [m['r2_640'] - m['r2_lu'] for m in matched]
bins = np.linspace(-1.4, 0.5, 30)
ax.hist(d640, bins=bins, color='#2196F3', alpha=0.5, label=f'640 (med={np.median(d640):+.3f})')
ax.hist(d1280, bins=bins, color='#FF5722', alpha=0.5, label=f'1280 (med={np.median(d1280):+.3f})')
ax.axvline(x=0, color='black', linewidth=1)
ax.set_xlabel('ΔR² (Ours - Lu)', fontsize=12)
ax.set_ylabel('Count', fontsize=12)
ax.set_title("(d) R² gap vs Lu", fontsize=12, fontweight='bold')
ax.legend(fontsize=10); ax.grid(True, alpha=0.3)

plt.suptitle('1280 (current best, ~120/300 ep) vs 640 vs Lu et al. 2025', fontsize=14, fontweight='bold', y=1.01)
plt.tight_layout()
plt.savefig(ROOT / 'results/compare_1280_640_lu.png', dpi=200, bbox_inches='tight')

# Text summary
print(f"\n{'='*65}")
print(f"  1280 (current, ~120/300 ep) vs 640 (1000 ep) vs Lu (seed=1)")
print(f"{'='*65}")
print(f"{'Metric':<22} {'1280':>10} {'640':>10} {'Lu':>10}")
print(f"{'-'*55}")
print(f"{'Global R2':<22} {np.mean([m['r2_1280']**2 for m in matched])**0.5 if False else '—':>10} {'—':>10} {'—':>10}")
# Simpler: just use medians
print(f"{'R2 median (all)':<22} {np.median([m['r2_1280'] for m in matched]):10.4f} {np.median([m['r2_640'] for m in matched]):10.4f} {np.median([m['r2_lu'] for m in matched]):10.4f}")
print(f"{'R2 median (idealized)':<22} {np.median([m['r2_1280'] for m in ideal]):10.4f} {np.median([m['r2_640'] for m in ideal]):10.4f} {np.median([m['r2_lu'] for m in ideal]):10.4f}")
print(f"{'R2 median (realistic)':<22} {np.median([m['r2_1280'] for m in real]):10.4f} {np.median([m['r2_640'] for m in real]):10.4f} {np.median([m['r2_lu'] for m in real]):10.4f}")
print(f"{'MAE mean (all)':<22} {np.mean([m['mae_1280'] for m in matched]):10.4f} {np.mean([m['mae_640'] for m in matched]):10.4f} {np.mean([m['mae_lu'] for m in matched]):10.4f}")
print(f"{'R2 wins vs Lu':<22} {r2_wins_1280:>10} {sum(1 for m in matched if m['r2_640']>=m['r2_lu']):>10} {len(matched)-r2_wins_1280:>10}")
print(f"{'R2 wins vs 640':<22} {wins_vs_640:>10} {'—':>10} {'—':>10}")
print(f"\nDone. Figure saved.")
