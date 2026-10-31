#!/usr/bin/env python3
"""Check R² distribution for 7-level model eval."""
import json, sys
sys.path.insert(0, '/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset/scripts')
sys.path.insert(0, '/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset/references')

# We need to save the per-case results from the eval. Let me re-run and save.
import numpy as np, torch, re
from pathlib import Path
import pandas as pd, xarray as xr
from unet_lu_7level import UNetLu7Level
from data_formatter_fixed import DataFormatterFixed as DataFormatter

ROOT = Path('/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset')
RAW_DIR = Path('/groups/kareem/[用户]/graph-deeponet-wind/data/urbantales/raw')

data = torch.load(ROOT / 'data/full_masked_640/test.pt', map_location='cpu', weights_only=False)
X, Y = data["X"], data["Y"]

model = UNetLu7Level(n_c=16)
model.load_state_dict(torch.load(ROOT / 'results/full_masked_640_7level/seed_1/model_best.pt', map_location='cpu', weights_only=True))
model.eval()

from torch.utils.data import DataLoader, TensorDataset
loader = DataLoader(TensorDataset(X), batch_size=2, shuffle=False)
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

formatter = DataFormatter(raw_data=raw_data_list, wind_angles=wind_angle_list, formatted_shape=640)
restored = formatter.restore_raw_output_data(pred_np[:, np.newaxis, :, :])

r2_values = []
for i, cn in enumerate(loaded_names):
    truth = raw_data_list[i]
    pred = restored[i]
    if truth.shape != pred.shape:
        if truth.shape == pred.T.shape: pred = pred.T
        else: continue
    valid = truth >= 0
    valid = valid & np.isfinite(truth) & np.isfinite(pred)
    t = truth[valid]; p = pred[valid]
    if len(t) == 0: continue
    ss_res = float(np.sum((t - p)**2)); ss_tot = float(np.sum((t - t.mean())**2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    r2_values.append((cn, r2))

# Print distribution
r2s = [r[1] for r in r2_values]
print(f"Total cases: {len(r2s)}")
print(f"Min R²: {min(r2s):.4f}")
print(f"Max R²: {max(r2s):.4f}")
print(f"Mean R²: {np.mean(r2s):.4f}")
print(f"Median R²: {np.median(r2s):.4f}")
print(f"Negative R² (<0): {sum(1 for r in r2s if r < 0)}")
print(f"R² < 0.1: {sum(1 for r in r2s if r < 0.1)}")
print(f"R² < 0: {sum(1 for r in r2s if r < 0)} / {len(r2s)}")

# Show worst cases
worst = sorted(r2_values, key=lambda x: x[1])
print(f"\nWorst 10 cases:")
for cn, r2 in worst[:10]:
    cat = "ideal" if cn.startswith(('VA','VS','UA','US')) else "realistic"
    print(f"  {cn:<35} R²={r2:.4f} ({cat})")
