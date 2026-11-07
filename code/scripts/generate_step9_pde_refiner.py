#!/usr/bin/env python3
"""Generate PDE-Refiner experiment configs (8 runs)."""
import json, os

CRC = "/groups/kareem/[用户]/graph-deeponet-wind/auto_v3"
CAMP = "step9_pde_refiner"

# Best UNet checkpoint from Step 1 run_01
BASE_MODEL = f"{CRC}/campaigns/grid18/run_01/model_best.pt"

L8 = [
    (0,0,0,0),(0,0,1,1),(0,1,0,1),(0,1,1,0),
    (1,0,0,1),(1,0,1,0),(1,1,0,0),(1,1,1,1),
]

SCHEDULE = ["linear", "cosine"]
STEPS = [2, 4]
WIDTH = ["full", "half"]
LR = [1e-4, 5e-4]

def build(rid, schedule, steps, width, lr):
    return {
        "experiment_id": f"pde_refiner_{rid:02d}",
        "strategy": "pde_refiner",
        "seed": 1, "epochs": 200, "lr": lr, "batch_size": 16,
        "checkpoint_interval": 50,
        "arch_name": "unet_v2_baseline",  # placeholder
        "arch_kwargs": {
            "base_model_path": BASE_MODEL,
            "base_arch_name": "unet_v2_baseline",
            "base_n_c": 16,
            "base_depth": 7,
            "refine_steps": steps,
            "noise_schedule": schedule,
            "max_noise": 0.5,
            "refiner_width": width,
        },
        "loss_name": "masked_l1",
        "loss_kwargs": {},
        "data_dir": f"{CRC}/shared/data",
        "results_dir": f"{CRC}/campaigns/{CAMP}/run_{rid:02d}",
        "split_manifest_path": f"{CRC}/shared/data/split_manifest.json",
        "heartbeat_interval_epochs": 50,
        "phase": "search", "eval_splits": ["val"],
    }

def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "campaigns", CAMP)
    for i, (s, st, w, lr_idx) in enumerate(L8):
        cfg = build(i, SCHEDULE[s], STEPS[st], WIDTH[w], LR[lr_idx])
        d = os.path.join(out, f"run_{i:02d}"); os.makedirs(d, exist_ok=True)
        json.dump(cfg, open(os.path.join(d, "train_config.json"), "w"), indent=2)
    print(f"Wrote 8 configs to {out}")

if __name__ == "__main__":
    main()
