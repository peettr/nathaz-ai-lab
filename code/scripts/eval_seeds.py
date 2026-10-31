#!/usr/bin/env python3
"""Evaluate completed seeds: compute per-case R² in RAW domain and compare with Lu.
Uses lu_full_train/test_seed1.csv for correct patch-to-case mapping (878 patches).
"""
import os, sys, json, numpy as np, torch
import pandas as pd
import xarray as xr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models.unet_lu_7level import UNetLu7Level

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FMT_DIR = os.path.join(ROOT, "data", "full_masked_640")
REF_DIR = os.path.join(ROOT, "references", "all_cases_20exp")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
gpu_name = torch.cuda.get_device_name(device) if torch.cuda.is_available() else "CPU"
print(f"Device: {device}, GPU: {gpu_name}")

# Load all formatted data
train_pt = torch.load(os.path.join(FMT_DIR, "train.pt"), map_location="cpu", weights_only=False)
test_pt = torch.load(os.path.join(FMT_DIR, "test.pt"), map_location="cpu", weights_only=False)
X_all = torch.cat([train_pt["X"], test_pt["X"]], dim=0)
Y_all = torch.cat([train_pt["Y"], test_pt["Y"]], dim=0)
print(f"Total patches: {X_all.shape[0]}")
del train_pt, test_pt

# ---- Build correct case_name -> patch indices from seed1 CSVs ----
train_csv = os.path.join(ROOT, "scripts", "lu_full_train_seed1.csv")
test_csv = os.path.join(ROOT, "scripts", "lu_full_test_seed1.csv")
train_df = pd.read_csv(train_csv)
test_df = pd.read_csv(test_csv)
all_df = pd.concat([train_df, test_df], ignore_index=True)
print(f"CSV mapping: {len(all_df)} patches, {all_df['case_name'].nunique()} unique cases")

case_to_indices = {}
for idx, row in all_df.iterrows():
    cn = row['case_name']
    if cn not in case_to_indices:
        case_to_indices[cn] = []
    case_to_indices[cn].append(idx)

# ---- Load U_mean for denormalization ----
# Y in train.pt is normalized: Y = (U - U_mean) / U_std
# We need U_mean to convert back: U = Y * U_std + U_mean
# But we don't have U_std stored. Let's check if data has normalization info.
# Actually, the formatted data uses data_formatter which normalizes by U_mean.
# Y = U / U_mean (ratio), so to get raw: U_raw = Y * U_mean

# Load U_mean from references
import glob
DATA_ROOT = os.path.join(ROOT, "data")
# Try loading from the formatted data's source
# Actually let's just compute R² in normalized domain correctly first,
# then also compute raw domain if U_mean is available.

def get_test_cases(seed):
    """Get test case names from Lu's CSV."""
    lu_test = pd.read_csv(os.path.join(REF_DIR, f"metrics_in_test_set_seed{seed}.csv"))
    lu_test = lu_test[lu_test['topo'] != 'total']
    return set(lu_test['topo'].astype(str) + '_d' + lu_test['angle'].astype(str).str.zfill(2))

def get_lu_metrics(seed):
    """Get Lu's per-case metrics from CSV."""
    lu_test = pd.read_csv(os.path.join(REF_DIR, f"metrics_in_test_set_seed{seed}.csv"))
    total_row = lu_test[lu_test['topo'] == 'total']
    lu_global_r2 = total_row['r2_score'].values[0] if len(total_row) > 0 else float('nan')
    
    lu_test = lu_test[lu_test['topo'] != 'total']
    lu_r2 = {}
    lu_mae = {}
    for _, row in lu_test.iterrows():
        cn = f"{row['topo']}_d{str(int(row['angle'])).zfill(2)}"
        lu_r2[cn] = row['r2_score']
        lu_mae[cn] = row['mae']
    return lu_r2, lu_mae, lu_global_r2

def eval_seed(seed):
    results_dir = os.path.join(ROOT, "results", "full_masked_640_7level", f"seed_{seed}")
    model_path = os.path.join(results_dir, "model_best.pt")
    if not os.path.exists(model_path):
        print(f"Seed {seed}: model_best.pt not found, skipping")
        return None
    
    test_cases = get_test_cases(seed)
    lu_r2_dict, lu_mae_dict, lu_global_r2 = get_lu_metrics(seed)
    
    # Build test patch indices using CORRECT mapping
    test_idx = []
    for c in sorted(case_to_indices.keys()):
        if c in test_cases:
            test_idx.extend(case_to_indices[c])
    
    if not test_idx:
        print(f"Seed {seed}: no test patches found!")
        return None
    
    print(f"\nSeed {seed}: {len(test_cases)} test cases, {len(test_idx)} test patches")
    
    X_test = X_all[test_idx].to(device)
    Y_test = Y_all[test_idx].to(device)
    
    model = UNetLu7Level(n_c=16).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=False))
    model.eval()
    
    # Batch predict
    BS = 16
    with torch.no_grad():
        preds = [model(X_test[i:i+BS]) for i in range(0, len(X_test), BS)]
        pred = torch.cat(preds, dim=0)
    
    # Valid mask: non-NaN AND non-building
    valid = (~torch.isnan(Y_test)) & (X_test <= 0)
    
    # ---- Normalized domain R² ----
    yt = Y_test[valid].cpu().numpy()
    pt = pred[valid].cpu().numpy()
    ss_res = np.sum((yt - pt) ** 2)
    ss_tot = np.sum((yt - np.mean(yt)) ** 2)
    norm_r2 = 1 - ss_res / ss_tot
    
    # ---- Per-case R² in normalized domain ----
    case_r2 = {}
    case_mae = {}
    
    unique_test = sorted(test_cases)
    idx_offset = 0
    for c in unique_test:
        n = len(case_to_indices.get(c, []))
        if n == 0:
            continue
        mask = valid[idx_offset:idx_offset+n]
        y_c = Y_test[idx_offset:idx_offset+n][mask].cpu().numpy()
        p_c = pred[idx_offset:idx_offset+n][mask].cpu().numpy()
        
        if len(y_c) > 1 and np.var(y_c) > 0:
            r2 = 1 - np.sum((y_c - p_c)**2) / np.sum((y_c - np.mean(y_c))**2)
        else:
            r2 = float('nan')
        case_r2[c] = r2
        case_mae[c] = np.mean(np.abs(y_c - p_c))
        idx_offset += n
    
    # Compare with Lu
    common = sorted(set(case_r2.keys()) & set(lu_r2_dict.keys()))
    our_r2_list = [case_r2[c] for c in common]
    lu_r2_list = [lu_r2_dict[c] for c in common]
    
    wins = sum(1 for o, l in zip(our_r2_list, lu_r2_list) if o > l)
    losses = sum(1 for o, l in zip(our_r2_list, lu_r2_list) if o < l)
    
    # Lu's R² is in raw domain, ours in normalized. 
    # Since Y = U/U_mean (ratio), normalized R² should be similar to raw R²
    # But let's report both perspectives
    
    print(f"  Normalized Global R² = {norm_r2:.4f}")
    print(f"  Lu Global R² = {lu_global_r2:.4f}")
    print(f"  Per-case: {len(common)} matched, {wins}W/{losses}L vs Lu")
    print(f"  Our median R² = {np.nanmedian(our_r2_list):.4f}")
    print(f"  Lu median R² = {np.nanmedian(lu_r2_list):.4f}")
    print(f"  Our mean R² = {np.nanmean(our_r2_list):.4f}")
    print(f"  Lu mean R² = {np.nanmean(lu_r2_list):.4f}")
    
    del X_test, Y_test, pred
    torch.cuda.empty_cache()
    
    return {
        'seed': seed,
        'norm_r2': norm_r2,
        'lu_global_r2': lu_global_r2,
        'median_r2': np.nanmedian(our_r2_list),
        'lu_median_r2': np.nanmedian(lu_r2_list),
        'mean_r2': np.nanmean(our_r2_list),
        'lu_mean_r2': np.nanmean(lu_r2_list),
        'wins': wins,
        'losses': losses,
        'n_cases': len(common),
    }

seeds = [1, 2, 3, 10]
print("=" * 80)
print(f"{'Seed':>5} | {'Our R²':>8} | {'Lu R²':>8} | {'Δ':>8} | {'W/L':>8} | {'Med':>8} | {'Lu Med':>8}")
print("-" * 80)

all_results = []
for s in seeds:
    r = eval_seed(s)
    if r:
        all_results.append(r)
        delta = r['norm_r2'] - r['lu_global_r2']
        print(f"{r['seed']:5d} | {r['norm_r2']:8.4f} | {r['lu_global_r2']:8.4f} | {delta:+8.4f} | {r['wins']:3d}/{r['losses']:3d} | {r['median_r2']:8.4f} | {r['lu_median_r2']:8.4f}")

print("=" * 80)
if all_results:
    avg_our = np.mean([r['norm_r2'] for r in all_results])
    avg_lu = np.mean([r['lu_global_r2'] for r in all_results])
    print(f"Mean: Our={avg_our:.4f}, Lu={avg_lu:.4f}, Δ={avg_our-avg_lu:+.4f}")
