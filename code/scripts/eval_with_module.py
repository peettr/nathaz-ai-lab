#!/usr/bin/env python3
"""Use eval_module.py (same as morning eval) to compare baselines."""
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
    "old_baseline_1000ep": f"{BASE}/campaigns/baseline/reference_seed7",
    "new_baseline_1000ep_l40s": f"{BASE}/campaigns/grid18_top3_1k/baseline",
}

for name, run_dir in models_to_eval.items():
    model_path = f"{run_dir}/model_best.pt"
    if not os.path.exists(model_path):
        print(f"\n{name}: model_best.pt not found")
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

    # Use eval_module's evaluate method
    for split in ["val", "holdout"]:
        result = eval_mod.evaluate(model, split=split, device=device, seed=1)
        print(f"\n{name} ({split}):")
        print(f"  R² median: {result['r2_median']:.4f}")
        print(f"  R² mean:   {result.get('r2_mean', 0):.4f}")
        print(f"  MAE median:{result.get('mae_median', 0):.4f}")
        print(f"  Cases:     {result.get('n_cases', '?')}")

    del model
    torch.cuda.empty_cache()
