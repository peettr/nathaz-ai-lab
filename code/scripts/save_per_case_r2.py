#!/usr/bin/env python3
"""Save per-case R² for all 20 seeds to JSON, then we can plot locally."""
import os, sys, re, json, numpy as np, torch
import pandas as pd, xarray as xr
from pathlib import Path
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path('/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset')
RAW_DIR = Path('/groups/kareem/[用户]/graph-deeponet-wind/data/urbantales/raw')
REF_DIR = ROOT / 'references' / 'all_cases_20exp'

sys.path.insert(0, str(ROOT / 'scripts' / 'models'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'references'))
from unet_lu_7level import UNetLu7Level
from data_formatter_fixed import DataFormatterFixed as DataFormatter

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {device}, GPU: {torch.cuda.get_device_name(device)}")

# Load all patches
train_pt = torch.load(ROOT / 'data/full_masked_640/train.pt', map_location='cpu', weights_only=False)
test_pt = torch.load(ROOT / 'data/full_masked_640/test.pt', map_location='cpu', weights_only=False)
X_all = torch.cat([train_pt["X"], test_pt["X"]], dim=0)

# Build patch_to_case mapping
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

# Load raw data
print("Loading raw data...")
all_raw = {}
for cn in sorted(case_to_patches.keys()):
    case_dir = RAW_DIR / cn
    if not case_dir.is_dir():
        continue
    try:
        topo = np.flipud(np.loadtxt(case_dir / f"{cn}_topo", dtype=np.float32))
        with xr.open_dataset(case_dir / f"{cn}_ped.nc") as ds:
            Uped = ds["Uped"].values.astype(np.float32)
        combined = Uped.copy()
        combined[topo > 0] = -topo[topo > 0]
        m = re.search(r"_d(\d+)$", cn)
        angle = int(m.group(1))
        all_raw[cn] = (combined, angle)
    except Exception as e:
        print(f"  Failed: {cn}: {e}")
print(f"Loaded {len(all_raw)} raw cases")


def predict_all(model_path):
    model = UNetLu7Level(n_c=16).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    model.eval()
    loader = DataLoader(TensorDataset(X_all.to(device)), batch_size=16, shuffle=False)
    all_pred = []
    with torch.no_grad():
        for (x,) in loader:
            all_pred.append(model(x))
    pred = np.nan_to_num(
        torch.cat(all_pred, dim=0).cpu().numpy()[:, 0, :, :],
        nan=0.0).astype(np.float32)
    del model
    torch.cuda.empty_cache()
    return pred


def restore_and_r2(cn, pred_all):
    if cn not in all_raw or cn not in case_to_patches:
        return float('nan'), float('nan')
    combined, angle = all_raw[cn]
    patch_indices = case_to_patches[cn]
    n_patches = len(patch_indices)
    formatter = DataFormatter(raw_data=[combined], wind_angles=[angle], formatted_shape=640)
    expected_n = formatter._fmt_input_data.shape[0]
    if n_patches != expected_n:
        return float('nan'), float('nan')
    pred_patches = np.stack([pred_all[i] for i in patch_indices], axis=0)
    pred_input = pred_patches[:, np.newaxis, :, :]
    restored = formatter.restore_raw_output_data(pred_input)
    pred_raw = np.nanmean(restored, axis=0)
    truth = combined
    if truth.shape != pred_raw.shape:
        if truth.shape == pred_raw.T.shape:
            pred_raw = pred_raw.T
        else:
            return float('nan'), float('nan')
    valid = (truth >= 0) & np.isfinite(truth) & np.isfinite(pred_raw)
    t = truth[valid]
    p = pred_raw[valid]
    if len(t) == 0:
        return float('nan'), float('nan')
    mae = float(np.mean(np.abs(t - p)))
    ss_res = float(np.sum((t - p) ** 2))
    ss_tot = float(np.sum((t - t.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float('nan')
    return r2, mae


all_results = {}

for seed in range(1, 21):
    res_dir = ROOT / f'results/full_masked_640_7level/seed_{seed}'
    model_path = res_dir / 'model_best.pt'
    if not model_path.exists():
        print(f"Seed {seed}: missing model")
        continue

    print(f"\n=== Seed {seed} ===")
    pred_np = predict_all(model_path)

    # Get test cases
    lu_test = pd.read_csv(REF_DIR / f"metrics_in_test_set_seed{seed}.csv")
    lu_test = lu_test[lu_test['topo'] != 'total']
    test_cases = set(lu_test['topo'].astype(str) + '_d' + lu_test['angle'].astype(str).str.zfill(2))

    # Get Lu per-case R²
    lu_r2_map = {}
    lu_mae_map = {}
    for _, row in lu_test.iterrows():
        cn = f"{row['topo']}_d{str(int(row['angle'])).zfill(2)}"
        lu_r2_map[cn] = float(row['r2_score'])
        lu_mae_map[cn] = float(row['mae'])

    # Compute our per-case R²
    per_case = []
    for cn in sorted(test_cases):
        our_r2, our_mae = restore_and_r2(cn, pred_np)
        per_case.append({
            'case': cn,
            'our_r2': float(our_r2),
            'lu_r2': lu_r2_map.get(cn, float('nan')),
            'our_mae': float(our_mae),
            'lu_mae': lu_mae_map.get(cn, float('nan')),
        })

    # Compute global R²
    all_t, all_p = [], []
    for entry in per_case:
        cn = entry['case']
        if cn not in all_raw or cn not in case_to_patches:
            continue
        combined, angle = all_raw[cn]
        patch_indices = case_to_patches[cn]
        pred_patches = np.stack([pred_np[i] for i in patch_indices], axis=0)
        formatter = DataFormatter(raw_data=[combined], wind_angles=[angle], formatted_shape=640)
        pred_input = pred_patches[:, np.newaxis, :, :]
        restored = formatter.restore_raw_output_data(pred_input)
        pred_raw = np.nanmean(restored, axis=0)
        if combined.shape != pred_raw.shape:
            if combined.shape == pred_raw.T.shape:
                pred_raw = pred_raw.T
            else:
                continue
        valid = (combined >= 0) & np.isfinite(combined) & np.isfinite(pred_raw)
        all_t.append(combined[valid])
        all_p.append(pred_raw[valid])

    all_t = np.concatenate(all_t)
    all_p = np.concatenate(all_p)
    global_r2 = 1 - np.sum((all_t - all_p)**2) / np.sum((all_t - all_t.mean())**2)

    wins = sum(1 for e in per_case if e['our_r2'] > e['lu_r2'])
    losses = sum(1 for e in per_case if e['our_r2'] < e['lu_r2'])

    all_results[str(seed)] = {
        'global_r2': float(global_r2),
        'per_case': per_case,
        'wins': wins,
        'losses': losses,
    }
    print(f"  Global R² = {global_r2:.4f}, W/L = {wins}/{losses}")

    del pred_np

# Save
out_path = ROOT / 'results' / 'per_case_r2_20seeds.json'
with open(out_path, 'w') as f:
    json.dump(all_results, f, indent=2)
print(f"\nSaved to {out_path}")
