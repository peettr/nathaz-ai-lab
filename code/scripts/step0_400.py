#!/usr/bin/env python3
"""
Full dataset data prep: Lu's seed=1 split, fmt_shape=400, masked loss (NaN excluded, building excluded).
"""
import json, torch, sys, re
import numpy as np
from pathlib import Path
import pandas as pd, xarray as xr

sys.path.insert(0, '/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset/references')
from data_formatter import DataFormatter

RAW_DIR = Path('/groups/kareem/[用户]/graph-deeponet-wind/data/urbantales/raw')
FMT = 400
DATA_DIR = Path(f'/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset/data/full_masked_{FMT}')

def load_combined_with_nan(case_dir, case_name):
    topo = np.flipud(np.loadtxt(case_dir / f"{case_name}_topo", dtype=np.float32))
    with xr.open_dataset(case_dir / f"{case_name}_ped.nc") as ds:
        Uped = ds["Uped"].values.astype(np.float32)
    combined = Uped.copy()
    combined[topo > 0] = -topo[topo > 0]
    return combined

# Load Lu's split
split_dir = Path('/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset/scripts')
train_df = pd.read_csv(split_dir / 'lu_full_train_seed1.csv')
test_df = pd.read_csv(split_dir / 'lu_full_test_seed1.csv')
lu_train = set(train_df['case_name'].tolist())
lu_test = set(test_df['case_name'].tolist())
print(f"Lu split: train={len(lu_train)}, test={len(lu_test)}")

# Load all cases
all_cases = {}
errors = []
for d in sorted(RAW_DIR.iterdir()):
    if not d.is_dir(): continue
    nm = d.name
    m = re.search(r"_d(\d+)$", nm)
    if not m: continue
    try:
        combined = load_combined_with_nan(d, nm)
        all_cases[nm] = dict(name=nm, combined=combined, wind_angle=int(m.group(1)))
    except Exception as e:
        errors.append(f"{nm}: {e}")

print(f"Loaded {len(all_cases)} cases ({len(errors)} errors)")

train_cases = [all_cases[n] for n in sorted(lu_train) if n in all_cases]
test_cases = [all_cases[n] for n in sorted(lu_test) if n in all_cases]
missing = sorted((lu_train | lu_test) - set(all_cases.keys()))
if missing: print(f"Missing: {missing}")

train_ideal = sum(1 for c in train_cases if c['name'].startswith(('VA','VS','UA','US')))
test_ideal = sum(1 for c in test_cases if c['name'].startswith(('VA','VS','UA','US')))
print(f"Train={len(train_cases)} ({train_ideal} ideal + {len(train_cases)-train_ideal} real)")
print(f"Test={len(test_cases)} ({test_ideal} ideal + {len(test_cases)-test_ideal} real)")

def format_cases(cases, fmt_shape):
    raw_data = [c["combined"] for c in cases]
    wind_angles = [c["wind_angle"] for c in cases]
    formatter = DataFormatter(raw_data=raw_data, wind_angles=wind_angles, formatted_shape=fmt_shape)
    X_fmt = formatter.get_formatted_input_data().astype(np.float32)
    Y_fmt = formatter.get_formatted_output_data()
    nan_mask = np.isnan(Y_fmt)
    X_clean = np.nan_to_num(X_fmt, nan=0.0).astype(np.float32)
    patch_to_case = []
    for ci, sr in enumerate(formatter._slice_indices):
        patch_to_case.extend([ci] * len(sr))
    return {
        "X": torch.from_numpy(X_clean).float(),
        "Y": torch.from_numpy(Y_fmt).float(),
        "nan_mask": torch.from_numpy(nan_mask).bool(),
        "case_names": [c["name"] for c in cases],
        "wind_angles": wind_angles,
        "patch_to_case": torch.tensor(patch_to_case, dtype=torch.long),
        "fmt_shape": fmt_shape,
    }

print(f"\nFormatting fmt_shape={FMT}...")
train_p = format_cases(train_cases, FMT)
test_p = format_cases(test_cases, FMT)
print(f"Train: X={train_p['X'].shape}, NaN={train_p['nan_mask'].sum().item()}")
print(f"Test:  X={test_p['X'].shape}, NaN={test_p['nan_mask'].sum().item()}")

DATA_DIR.mkdir(parents=True, exist_ok=True)
torch.save(train_p, DATA_DIR / 'train.pt')
torch.save(test_p, DATA_DIR / 'test.pt')
with open(DATA_DIR / 'meta.json', 'w') as f:
    json.dump(dict(fmt_shape=FMT, n_train=len(train_cases), n_test=len(test_cases),
                   train_cases=[c["name"] for c in train_cases],
                   test_cases=[c["name"] for c in test_cases]), f, indent=2)
print(f"Saved to {DATA_DIR}")
print("Done!")
