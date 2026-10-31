#!/usr/bin/env python3
"""Quick R² evaluation for top3_1k runs (current best checkpoints)."""
import json, os, sys
import torch
import numpy as np

BASE = "/groups/kareem/[用户]/graph-deeponet-wind/auto_v3"
DATA_DIR = f"{BASE}/shared/data"
RUN_DIR = f"{BASE}/campaigns/grid18_top3_1k"

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

sys.path.insert(0, f"{BASE}/shared")
from models.unet_v2_baseline import UNetV2Baseline

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
print(f"Device: {device} ({gpu})")

X_val = X_val.to(device)
Y_val = Y_val.to(device)

def evaluate(model, X, Y, cases):
    model.eval()
    case_indices = {}
    for i, cn in enumerate(cases):
        if cn not in case_indices:
            case_indices[cn] = []
        case_indices[cn].append(i)
    
    r2s = []
    maes = []
    with torch.no_grad():
        for cn in sorted(case_indices.keys()):
            idx = case_indices[cn]
            x = X[idx]
            y = Y[idx]
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
    return np.median(r2s), np.mean(r2s), np.median(maes), np.mean(maes)

runs = ["baseline", "run_02", "run_11", "run_17"]
for name in runs:
    cfg_path = f"{RUN_DIR}/{name}/train_config.json"
    model_path = f"{RUN_DIR}/{name}/model_best.pt"
    if not os.path.exists(model_path):
        print(f"{name}: no model yet")
        continue
    
    with open(cfg_path) as f:
        cfg = json.load(f)
    n_c = cfg.get("arch_kwargs", {}).get("n_c", 16)
    loss_name = cfg.get("loss_name", "?")
    
    model = UNetV2Baseline(n_c=n_c)
    state = torch.load(model_path, map_location="cpu", weights_only=False)
    model.load_state_dict(state if "model_state_dict" not in state else state["model_state_dict"])
    model = model.to(device)
    
    r2_med, r2_mean, mae_med, mae_mean = evaluate(model, X_val, Y_val, val_cases)
    print(f"{name}: n_c={n_c} loss={loss_name} R²_med={r2_med:.4f} R²_mean={r2_mean:.4f} MAE_med={mae_med:.4f} MAE_mean={mae_mean:.4f}")
    
    del model
    torch.cuda.empty_cache()
