#!/usr/bin/env python3
"""
Evaluate seeds in RAW domain using patch_to_case for correct mapping.
For each case: collect ALL its patches, pass to DataFormatter.restore_raw_output_data.
"""
import os, sys, re, json, numpy as np, torch
import pandas as pd, xarray as xr
from pathlib import Path
from torch.utils.data import DataLoader, TensorDataset
from collections import Counter

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

# ---- Load all formatted data ----
train_pt = torch.load(ROOT / 'data/full_masked_640/train.pt', map_location='cpu', weights_only=False)
test_pt = torch.load(ROOT / 'data/full_masked_640/test.pt', map_location='cpu', weights_only=False)
X_all = torch.cat([train_pt["X"], test_pt["X"]], dim=0)  # 878 patches

# Build per-patch case name using patch_to_case
train_cn = train_pt["case_names"]
test_cn = test_pt["case_names"]
train_p2c = train_pt["patch_to_case"]
test_p2c = test_pt["patch_to_case"]

patch_case_names = []
for i in range(len(train_p2c)):
    patch_case_names.append(train_cn[int(train_p2c[i])])
for i in range(len(test_p2c)):
    patch_case_names.append(test_cn[int(test_p2c[i])])

# case -> [patch_indices] in order
case_to_patches = {}
for idx, cn in enumerate(patch_case_names):
    if cn not in case_to_patches:
        case_to_patches[cn] = []
    case_to_patches[cn].append(idx)

print(f"Total patches: {X_all.shape[0]}, Unique cases: {len(case_to_patches)}")
del train_pt, test_pt

# ---- Load ALL raw data ----
print("Loading raw data for all cases...")
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


def get_test_cases(seed):
    lu_test = pd.read_csv(REF_DIR / f"metrics_in_test_set_seed{seed}.csv")
    lu_test = lu_test[lu_test['topo'] != 'total']
    return set(lu_test['topo'].astype(str) + '_d' + lu_test['angle'].astype(str).str.zfill(2))

def get_lu_metrics(seed):
    lu_test = pd.read_csv(REF_DIR / f"metrics_in_test_set_seed{seed}.csv")
    total = lu_test[lu_test['topo'] == 'total']
    lu_global = total['r2_score'].values[0] if len(total) > 0 else float('nan')
    lu_test = lu_test[lu_test['topo'] != 'total']
    lu_r2 = {}
    for _, row in lu_test.iterrows():
        cn = f"{row['topo']}_d{str(int(row['angle'])).zfill(2)}"
        lu_r2[cn] = row['r2_score']
    return lu_r2, lu_global


def predict_all(model_path):
    model = UNetLu7Level(n_c=16).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    model.eval()
    loader = DataLoader(TensorDataset(X_all.to(device)), batch_size=4, shuffle=False)
    all_pred = []
    with torch.no_grad():
        for (x,) in loader:
            all_pred.append(model(x))
    pred = np.nan_to_num(torch.cat(all_pred, dim=0).cpu().numpy()[:, 0, :, :], nan=0.0).astype(np.float32)
    del model
    torch.cuda.empty_cache()
    return pred


def restore_case(cn, pred_np):
    """Restore all patches for a case and compute R² vs raw truth."""
    if cn not in all_raw:
        return float('nan'), float('nan'), None, None
    combined, angle = all_raw[cn]
    patches = case_to_patches[cn]
    
    # Collect predictions for this case's patches
    pred_patches = np.stack([pred_np[i] for i in patches], axis=0)  # (N, 640, 640)
    
    # Create formatter and restore
    formatter = DataFormatter(raw_data=[combined], wind_angles=[angle], formatted_shape=640)
    expected_n = formatter._fmt_input_data.shape[0]
    
    if pred_patches.shape[0] != expected_n:
        # Mismatch - try anyway with what we have
        if pred_patches.shape[0] < expected_n:
            # Pad with zeros
            pad = np.zeros((expected_n - pred_patches.shape[0], 640, 640), dtype=np.float32)
            pred_patches = np.concatenate([pred_patches, pad], axis=0)
    
    # Restore: input shape (N, 1, 640, 640)
    pred_input = pred_patches[:, np.newaxis, :, :]
    restored = formatter.restore_raw_output_data(pred_input)
    
    # restored shape: (N, H, W) - average all patches
    pred_avg = np.nanmean(restored, axis=0)
    truth = combined
    
    if truth.shape != pred_avg.shape:
        if truth.shape == pred_avg.T.shape:
            pred_avg = pred_avg.T
        else:
            return float('nan'), float('nan'), None, None
    
    valid = (truth >= 0) & np.isfinite(truth) & np.isfinite(pred_avg)
    t = truth[valid]
    p = pred_avg[valid]
    if len(t) == 0:
        return float('nan'), float('nan'), None, None
    
    mae = float(np.mean(np.abs(t - p)))
    ss_res = float(np.sum((t - p) ** 2))
    ss_tot = float(np.sum((t - t.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float('nan')
    return r2, mae, t, p


def eval_seed(seed, pred_np):
    res_dir = ROOT / f'results/full_masked_640_7level/seed_{seed}'
    model_path = res_dir / 'model_best.pt'
    if not model_path.exists():
        print(f"Seed {seed}: no model_best.pt")
        return None
    
    test_cases = get_test_cases(seed)
    lu_r2_dict, lu_global_r2 = get_lu_metrics(seed)
    
    print(f"\nSeed {seed}: {len(test_cases)} test cases from Lu")
    
    # Per-case R²
    case_r2 = {}
    case_mae = {}
    all_t, all_p = [], []
    
    for cn in sorted(test_cases):
        if cn not in case_to_patches:
            continue
        r2, mae, t, p = restore_case(cn, pred_np)
        if not np.isnan(r2):
            case_r2[cn] = r2
            case_mae[cn] = mae
            if t is not None:
                all_t.append(t)
                all_p.append(p)
    
    # Global R²
    all_t = np.concatenate(all_t)
    all_p = np.concatenate(all_p)
    global_r2 = 1 - np.sum((all_t - all_p)**2) / np.sum((all_t - all_t.mean())**2)
    global_mae = float(np.mean(np.abs(all_t - all_p)))
    
    # Compare with Lu
    common = sorted(set(case_r2.keys()) & set(lu_r2_dict.keys()))
    our_list = [case_r2[c] for c in common]
    lu_list = [lu_r2_dict[c] for c in common]
    wins = sum(1 for o, l in zip(our_list, lu_list) if o > l)
    losses = sum(1 for o, l in zip(our_list, lu_list) if o < l)
    
    print(f"  RAW Global R² = {global_r2:.4f}, MAE = {global_mae:.4f}")
    print(f"  Lu Global R² = {lu_global_r2:.4f}")
    print(f"  Per-case: {len(common)} matched, {wins}W/{losses}L")
    print(f"  Median: ours={np.nanmedian(our_list):.4f}, Lu={np.nanmedian(lu_list):.4f}")
    print(f"  Mean: ours={np.nanmean(our_list):.4f}, Lu={np.nanmean(lu_list):.4f}")
    
    return {
        'seed': seed,
        'global_r2': global_r2,
        'global_mae': global_mae,
        'lu_global_r2': lu_global_r2,
        'median_r2': np.nanmedian(our_list),
        'lu_median_r2': np.nanmedian(lu_list),
        'mean_r2': np.nanmean(our_list),
        'lu_mean_r2': np.nanmean(lu_list),
        'wins': wins,
        'losses': losses,
        'n_cases': len(common),
    }


seeds = [1, 2, 3, 4, 5, 10]
print("=" * 80)
print(f"{'Seed':>5} | {'Our R²':>8} | {'Lu R²':>8} | {'Δ':>8} | {'W/L':>8} | {'Med':>8} | {'Lu Med':>8}")
print("-" * 80)

results = []
for s in seeds:
    res_dir = ROOT / f'results/full_masked_640_7level/seed_{s}'
    model_path = res_dir / 'model_best.pt'
    if not model_path.exists():
        print(f"Seed {s}: skipping")
        continue
    pred_np = predict_all(model_path)
    r = eval_seed(s, pred_np)
    if r:
        results.append(r)
        d = r['global_r2'] - r['lu_global_r2']
        print(f"{r['seed']:5d} | {r['global_r2']:8.4f} | {r['lu_global_r2']:8.4f} | {d:+8.4f} | {r['wins']:3d}/{r['losses']:3d} | {r['median_r2']:8.4f} | {r['lu_median_r2']:8.4f}")

print("=" * 80)
if results:
    a = np.mean([r['global_r2'] for r in results])
    b = np.mean([r['lu_global_r2'] for r in results])
    print(f"Mean: Our={a:.4f}, Lu={b:.4f}, Δ={a-b:+.4f}")
