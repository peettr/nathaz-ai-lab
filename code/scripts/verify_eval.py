import numpy as np, sys, os, re, torch
import xarray as xr
from pathlib import Path
from collections import Counter

ROOT = Path('/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset')
RAW_DIR = Path('/groups/kareem/[用户]/graph-deeponet-wind/data/urbantales/raw')

sys.path.insert(0, str(ROOT / 'scripts' / 'models'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'references'))
from unet_lu_7level import UNetLu7Level
from data_formatter_fixed import DataFormatterFixed as DataFormatter

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {device}, GPU: {torch.cuda.get_device_name(device)}")

# ---- Step 1: Load ALL formatted data ----
train_pt = torch.load(ROOT / 'data/full_masked_640/train.pt', map_location='cpu', weights_only=False)
test_pt = torch.load(ROOT / 'data/full_masked_640/test.pt', map_location='cpu', weights_only=False)
X_all = torch.cat([train_pt["X"], test_pt["X"]], dim=0)  # 878

# Build per-patch case name using patch_to_case
train_cn = train_pt["case_names"]  # 410 names
test_cn = test_pt["case_names"]    # 102 names
train_p2c = train_pt["patch_to_case"]  # 705 -> 0..409
test_p2c = test_pt["patch_to_case"]    # 173 -> 0..101

patch_case_names = []
for i in range(len(train_p2c)):
    patch_case_names.append(train_cn[int(train_p2c[i])])
for i in range(len(test_p2c)):
    patch_case_names.append(test_cn[int(test_p2c[i])])

print(f"Total patches: {X_all.shape[0]}")
print(f"Unique cases via patch_to_case: {len(set(patch_case_names))}")

# case -> [patch_indices in X_all] 
case_to_patches = {}
for idx, cn in enumerate(patch_case_names):
    if cn not in case_to_patches:
        case_to_patches[cn] = []
    case_to_patches[cn].append(idx)

# ---- Step 2: Verify patch counts match DataFormatter expectations ----
print("\n=== Verifying patch counts vs DataFormatter ===")
mismatch = []
sample_cases = sorted(case_to_patches.keys())[:20]  # Check first 20

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
        formatter = DataFormatter(raw_data=[combined], wind_angles=[angle], formatted_shape=640)
        expected = formatter._fmt_input_data.shape[0]
        actual = len(case_to_patches[cn])
        if expected != actual:
            mismatch.append((cn, expected, actual))
    except:
        pass

print(f"Total cases checked: {len(set(patch_case_names))}")
print(f"Mismatches: {len(mismatch)}")
if mismatch:
    for cn, exp, act in mismatch[:10]:
        print(f"  {cn}: expected={exp}, actual={act}")

# ---- Step 3: Verify seed 1 eval matches compare_7lv_lu.py ----
print("\n=== Verifying Seed 1 eval ===")
import pandas as pd
import csv, io

REF_DIR = ROOT / 'references' / 'all_cases_20exp'

test_df = pd.read_csv(ROOT / 'scripts/lu_full_test_seed1.csv')
seed1_test_cases = sorted(test_df['case_name'].tolist())
print(f"Seed 1 test cases from CSV: {len(seed1_test_cases)}")

# Predict all
model = UNetLu7Level(n_c=16).to(device)
model.load_state_dict(torch.load(ROOT / 'results/full_masked_640_7level/seed_1/model_best.pt', map_location=device, weights_only=True))
model.eval()

from torch.utils.data import DataLoader, TensorDataset
loader = DataLoader(TensorDataset(X_all.to(device)), batch_size=4, shuffle=False)
all_pred = []
with torch.no_grad():
    for (x,) in loader:
        all_pred.append(model(x))
pred_all = np.nan_to_num(torch.cat(all_pred, dim=0).cpu().numpy()[:, 0, :, :], nan=0.0).astype(np.float32)
del model
torch.cuda.empty_cache()

# Method A: Like compare_7lv_lu.py (test.pt only, per-case restore)
print("\n--- Method A: test.pt patches, per-case restore (like compare_7lv_lu.py) ---")
test_pred = pred_all[705:]  # test_pt starts at index 705
case_r2_A = {}
for i, cn in enumerate(seed1_test_cases):
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
    except:
        continue
    
    n_patches = len(case_to_patches[cn])
    formatter = DataFormatter(raw_data=[combined], wind_angles=[angle], formatted_shape=640)
    expected_n = formatter._fmt_input_data.shape[0]
    
    if n_patches == 1:
        # Single patch case - use test_pred directly
        pred_patch = test_pred[i][np.newaxis, np.newaxis, :, :]
    else:
        # Multi-patch case - need ALL patches in order
        # These are contiguous in test_pt starting at position i
        pred_patches = test_pred[i:i+n_patches]
        pred_patch = pred_patches[:, np.newaxis, :, :]
    
    if pred_patch.shape[0] != expected_n:
        print(f"  Shape mismatch: {cn} pred={pred_patch.shape[0]} expected={expected_n}")
        continue
    
    restored = formatter.restore_raw_output_data(pred_patch)
    pred_raw = np.nanmean(restored, axis=0)
    truth = combined
    
    if truth.shape != pred_raw.shape:
        if truth.shape == pred_raw.T.shape:
            pred_raw = pred_raw.T
        else:
            continue
    
    valid = (truth >= 0) & np.isfinite(truth) & np.isfinite(pred_raw)
    t = truth[valid]; p = pred_raw[valid]
    if len(t) > 1 and np.var(t) > 0:
        r2 = 1 - np.sum((t-p)**2) / np.sum((t-t.mean())**2)
        case_r2_A[cn] = r2

# Method B: Using patch_to_case mapping (all patches)
print("\n--- Method B: patch_to_case mapping, all patches ---")
case_r2_B = {}
for cn in seed1_test_cases:
    if cn not in case_to_patches:
        continue
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
    except:
        continue
    
    patches = case_to_patches[cn]
    formatter = DataFormatter(raw_data=[combined], wind_angles=[angle], formatted_shape=640)
    expected_n = formatter._fmt_input_data.shape[0]
    
    pred_patches = np.stack([pred_all[i] for i in patches], axis=0)
    
    if pred_patches.shape[0] != expected_n:
        print(f"  Shape mismatch: {cn} pred={pred_patches.shape[0]} expected={expected_n}")
        continue
    
    pred_input = pred_patches[:, np.newaxis, :, :]
    restored = formatter.restore_raw_output_data(pred_input)
    pred_raw = np.nanmean(restored, axis=0)
    truth = combined
    
    if truth.shape != pred_raw.shape:
        if truth.shape == pred_raw.T.shape:
            pred_raw = pred_raw.T
        else:
            continue
    
    valid = (truth >= 0) & np.isfinite(truth) & np.isfinite(pred_raw)
    t = truth[valid]; p = pred_raw[valid]
    if len(t) > 1 and np.var(t) > 0:
        r2 = 1 - np.sum((t-p)**2) / np.sum((t-t.mean())**2)
        case_r2_B[cn] = r2

# Compare A vs B
common = sorted(set(case_r2_A.keys()) & set(case_r2_B.keys()))
print(f"\nMethod A cases: {len(case_r2_A)}, Method B cases: {len(case_r2_B)}, Common: {len(common)}")

diffs = [(cn, case_r2_A[cn], case_r2_B[cn], abs(case_r2_A[cn] - case_r2_B[cn])) for cn in common]
diffs.sort(key=lambda x: -x[3])
print("Top 10 diffs:")
for cn, a, b, d in diffs[:10]:
    print(f"  {cn}: A={a:.4f} B={b:.4f} diff={d:.4f}")

# Global R²
def global_r2(case_r2_dict, pred_all_or_test, use_all_patches=False):
    all_t, all_p = [], []
    for cn in sorted(case_r2_dict.keys()):
        case_dir = RAW_DIR / cn
        try:
            topo = np.flipud(np.loadtxt(case_dir / f"{cn}_topo", dtype=np.float32))
            with xr.open_dataset(case_dir / f"{cn}_ped.nc") as ds:
                Uped = ds["Uped"].values.astype(np.float32)
            combined = Uped.copy()
            combined[topo > 0] = -topo[topo > 0]
            m = re.search(r"_d(\d+)$", cn)
            angle = int(m.group(1))
        except:
            continue
        
        if use_all_patches:
            patches = case_to_patches[cn]
            pred_patches = np.stack([pred_all_or_test[i] for i in patches], axis=0)
        else:
            i = seed1_test_cases.index(cn)
            n_patches = len(case_to_patches[cn])
            pred_patches = pred_all_or_test[i:i+n_patches]
        
        formatter = DataFormatter(raw_data=[combined], wind_angles=[angle], formatted_shape=640)
        if pred_patches.shape[0] != formatter._fmt_input_data.shape[0]:
            continue
        pred_input = pred_patches[:, np.newaxis, :, :]
        restored = formatter.restore_raw_output_data(pred_input)
        pred_raw = np.nanmean(restored, axis=0)
        truth = combined
        if truth.shape != pred_raw.shape:
            if truth.shape == pred_raw.T.shape:
                pred_raw = pred_raw.T
            else:
                continue
        valid = (truth >= 0) & np.isfinite(truth) & np.isfinite(pred_raw)
        all_t.append(truth[valid])
        all_p.append(pred_raw[valid])
    
    all_t = np.concatenate(all_t)
    all_p = np.concatenate(all_p)
    return 1 - np.sum((all_t-all_p)**2) / np.sum((all_t-all_t.mean())**2)

gr2_A = global_r2(case_r2_A, test_pred, use_all_patches=False)
gr2_B = global_r2(case_r2_B, pred_all, use_all_patches=True)
print(f"\nGlobal R² Method A (test.pt): {gr2_A:.4f}")
print(f"Global R² Method B (patch_to_case): {gr2_B:.4f}")
print(f"Yesterday's result: 0.687")
