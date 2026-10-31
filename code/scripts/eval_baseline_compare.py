#!/usr/bin/env python3
"""Eval new baseline 1000ep (L40S) with the same eval script as morning."""
import json, os, sys
import torch
import numpy as np

BASE = "/groups/kareem/[用户]/graph-deeponet-wind/auto_v3"
DATA_DIR = f"{BASE}/shared/data"

# Morning eval used compare_grid18_baseline.py logic - same thing here
data = torch.load(f"{DATA_DIR}/all_data.pt", map_location="cpu", weights_only=False)
with open(f"{DATA_DIR}/split_manifest.json") as f:
    manifest = json.load(f)

sp = manifest["seeds"]["1"]
val_set = set(sp["val"])
p2c = data["patch_to_case"]
case_names = data["case_names"]

indices = [i for i in range(len(p2c)) if case_names[int(p2c[i])] in val_set]
idx_t = torch.tensor(indices, dtype=torch.long)
X_val = data["X"][idx_t]
Y_val = data["Y"][idx_t]
val_cases = [case_names[int(p2c[i])] for i in indices]

print(f"Val: {len(set(val_cases))} unique cases, {len(X_val)} patches")

sys.path.insert(0, f"{BASE}/shared")
from models.unet_v2_baseline import UNetV2Baseline

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
print(f"Device: {device} ({gpu})")

X_val = X_val.to(device)
Y_val = Y_val.to(device)

# Evaluate multiple models
models_to_eval = {
    "old_baseline_1000ep": f"{BASE}/campaigns/baseline/reference_seed7",
    "new_baseline_1000ep_l40s": f"{BASE}/campaigns/grid18_top3_1k/baseline",
}

for name, run_dir in models_to_eval.items():
    model_path = f"{run_dir}/model_best.pt"
    if not os.path.exists(model_path):
        print(f"\n{name}: model_best.pt not found, skipping")
        continue
    
    with open(f"{run_dir}/train_config.json") as f:
        cfg = json.load(f)
    n_c = cfg.get("arch_kwargs", {}).get("n_c", 16)
    
    model = UNetV2Baseline(n_c=n_c)
    state = torch.load(model_path, map_location="cpu", weights_only=False)
    if "model_state_dict" in state:
        state = state["model_state_dict"]
    model.load_state_dict(state)
    model = model.to(device)
    
    # Per-case R² and MAE
    model.eval()
    case_indices = {}
    for i, cn in enumerate(val_cases):
        if cn not in case_indices:
            case_indices[cn] = []
        case_indices[cn].append(i)
    
    r2s = []
    maes = []
    with torch.no_grad():
        for cn in sorted(case_indices.keys()):
            idx = case_indices[cn]
            x = X_val[idx]
            y = Y_val[idx]
            pred = torch.cat([model(x[i:i+1]) for i in range(len(x))], dim=0)
            mask = (~torch.isnan(y)) & (x <= 0)
            p_flat = pred[mask].cpu().numpy()
            t_flat = y[mask].cpu().numpy()
            if len(t_flat) < 10:
                continue
            ss_res = np.sum((p_flat - t_flat) ** 2)
            ss_tot = np.sum((t_flat - t_flat.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
            mae = np.mean(np.abs(p_flat - t_flat))
            r2s.append(r2)
            maes.append(mae)
    
    print(f"\n{name} (n_c={n_c}):")
    print(f"  R² median: {np.median(r2s):.4f}")
    print(f"  R² mean:   {np.mean(r2s):.4f}")
    print(f"  MAE median:{np.median(maes):.4f}")
    print(f"  MAE mean:  {np.mean(maes):.4f}")
    print(f"  Cases: {len(r2s)}")
    
    del model
    torch.cuda.empty_cache()
