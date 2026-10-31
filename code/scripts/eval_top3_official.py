#!/usr/bin/env python3
"""Eval all completed top3_1k runs with eval_module.py (official standard)."""
import json, os, sys
import torch
import numpy as np

BASE = "/groups/kareem/[用户]/graph-deeponet-wind/auto_v3"
DATA_DIR = f"{BASE}/shared/data"
sys.path.insert(0, f"{BASE}/shared")

from eval_module import EvalModule
from models.unet_v2_baseline import UNetV2Baseline

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
print(f"Device: {device} ({gpu})")

eval_mod = EvalModule(
    split_manifest_path=f"{DATA_DIR}/split_manifest.json",
    data_dir=DATA_DIR,
)

models_to_eval = {
    "baseline_1000ep": f"{BASE}/campaigns/grid18_top3_1k/baseline",
    "run_02_1000ep": f"{BASE}/campaigns/grid18_top3_1k/run_02",
    "run_17_1000ep": f"{BASE}/campaigns/grid18_top3_1k/run_17",
}

for name, run_dir in models_to_eval.items():
    model_path = f"{run_dir}/model_best.pt"
    if not os.path.exists(model_path):
        print(f"\n{name}: model_best.pt not found, skipping")
        continue

    with open(f"{run_dir}/train_config.json") as f:
        cfg = json.load(f)
    n_c = cfg.get("arch_kwargs", {}).get("n_c", 16)
    loss_name = cfg.get("loss_name", "?")

    model = UNetV2Baseline(n_c=n_c)
    state = torch.load(model_path, map_location="cpu", weights_only=False)
    if "model_state_dict" in state:
        state = state["model_state_dict"]
    model.load_state_dict(state)
    model = model.to(device)

    print(f"\n{'='*50}")
    print(f"{name}: n_c={n_c}, loss={loss_name}")
    
    for split in ["val", "holdout"]:
        result = eval_mod.evaluate(model, split=split, device=device, seed=1)
        print(f"  {split:8s}: R²_med={result['r2_median']:.4f} R²_mean={result.get('r2_mean',0):.4f} MAE_med={result.get('mae_median',0):.4f} cases={result.get('n_cases','?')}")

    del model
    torch.cuda.empty_cache()

# Also check run_11 if model exists
run11_path = f"{BASE}/campaigns/grid18_top3_1k/run_11/model_best.pt"
if os.path.exists(run11_path):
    with open(f"{BASE}/campaigns/grid18_top3_1k/run_11/train_config.json") as f:
        cfg = json.load(f)
    model = UNetV2Baseline(n_c=32)
    state = torch.load(run11_path, map_location="cpu", weights_only=False)
    if "model_state_dict" in state:
        state = state["model_state_dict"]
    model.load_state_dict(state)
    model = model.to(device)
    print(f"\n{'='*50}")
    print(f"run_11 (in progress): n_c=32, loss=masked_huber")
    for split in ["val", "holdout"]:
        result = eval_mod.evaluate(model, split=split, device=device, seed=1)
        print(f"  {split:8s}: R²_med={result['r2_median']:.4f} R²_mean={result.get('r2_mean',0):.4f} MAE_med={result.get('mae_median',0):.4f} cases={result.get('n_cases','?')}")
    del model
    torch.cuda.empty_cache()
