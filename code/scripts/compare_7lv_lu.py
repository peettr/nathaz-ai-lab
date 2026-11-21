#!/usr/bin/env python3
"""7-level vs Lu per-case R² comparison."""
import json, csv, io, numpy as np, torch, re
from pathlib import Path
import pandas as pd, xarray as xr

sys_path_add = '/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset'
import sys
sys.path.insert(0, sys_path_add + '/scripts/models')
sys.path.insert(0, sys_path_add + '/scripts')
sys.path.insert(0, sys_path_add + '/references')

from unet_lu_7level import UNetLu7Level
from data_formatter_fixed import DataFormatterFixed as DataFormatter

ROOT = Path(sys_path_add)
RAW_DIR = Path('/groups/kareem/[用户]/graph-deeponet-wind/data/urbantales/raw')

data = torch.load(ROOT / 'data/full_masked_640/test.pt', map_location='cpu', weights_only=False)
X = data["X"]

model = UNetLu7Level(n_c=16)
model.load_state_dict(torch.load(ROOT / 'results/full_masked_640_7level/seed_1/model_best.pt', map_location='cpu', weights_only=True))
model.eval()

from torch.utils.data import DataLoader, TensorDataset
loader = DataLoader(TensorDataset(X), batch_size=2, shuffle=False)
all_pred = []
with torch.no_grad():
    for (x,) in loader: all_pred.append(model(x))
pred_np = np.nan_to_num(torch.cat(all_pred, dim=0).numpy()[:, 0, :, :], nan=0.0).astype(np.float32)

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
        combined = Uped.copy(); combined[topo > 0] = -topo[topo > 0]
        m = re.search(r"_d(\d+)$", cn)
        raw_data_list.append(combined); wind_angle_list.append(int(m.group(1))); loaded_names.append(cn)
    except: pass

formatter = DataFormatter(raw_data=raw_data_list, wind_angles=wind_angle_list, formatted_shape=640)
restored = formatter.restore_raw_output_data(pred_np[:, np.newaxis, :, :])

r2_map_7 = {}
for i, cn in enumerate(loaded_names):
    truth = raw_data_list[i]; pred = restored[i]
    if truth.shape != pred.shape:
        if truth.shape == pred.T.shape: pred = pred.T
        else: continue
    valid = (truth >= 0) & np.isfinite(truth) & np.isfinite(pred)
    t = truth[valid]; p = pred[valid]
    if len(t) == 0: continue
    ss_res = float(np.sum((t-p)**2)); ss_tot = float(np.sum((t-t.mean())**2))
    r2_map_7[cn] = 1 - ss_res/ss_tot if ss_tot > 0 else 0.0

# Load 640 and Lu
with open(ROOT / 'results/full_masked_640/seed_1/metrics_raw_restore_best.json') as f:
    m640 = json.load(f)
r2_map_5 = {c['case_name']: c['r2'] for c in m640['by_case']}

lu_text = open(ROOT / 'references/all_cases_20exp/metrics_in_test_set_seed1.csv').read()
reader = csv.DictReader(io.StringIO(lu_text))
lu_map = {}
for row in reader:
    if row['topo'] == 'total': continue
    lu_map[(row['topo'], int(row['angle']))] = float(row['r2_score'])

# Match all three
print(f"{'Case':<35} {'5-lv':>8} {'7-lv':>8} {'Lu':>8} {'5ΔLu':>8} {'7ΔLu':>8}")
print("-" * 75)
matched = []
for cn in sorted(r2_map_7.keys()):
    cn_base = cn.rsplit('_d', 1)[0]; cn_angle = int(cn.rsplit('_d', 1)[1])
    lu_key = (cn_base, cn_angle)
    if lu_key not in lu_map: continue
    r7 = r2_map_7[cn]; r5 = r2_map_5.get(cn, 0); rl = lu_map[lu_key]
    matched.append((cn, r5, r7, rl))
    print(f"{cn:<35} {r5:8.4f} {r7:8.4f} {rl:8.4f} {r5-rl:+8.4f} {r7-rl:+8.4f}")

# Summary
print(f"\n{'='*55}")
w5 = sum(1 for c in matched if c[1] >= c[3])
w7 = sum(1 for c in matched if c[2] >= c[3])
print(f"5-level wins vs Lu: {w5}/{len(matched)}")
print(f"7-level wins vs Lu: {w7}/{len(matched)}")
print(f"7-level beats 5-level: {sum(1 for c in matched if c[2] > c[1])}/{len(matched)}")
print(f"5-level beats 7-level: {sum(1 for c in matched if c[1] > c[2])}/{len(matched)}")
