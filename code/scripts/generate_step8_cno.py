#!/usr/bin/env python3
"""Generate CNO experiment configs (13 runs)."""
import json, os

CRC = "/groups/kareem/[用户]/graph-deeponet-wind/auto_v3"
CAMP = "step8_cno"

L12 = [
    (0,0,0,0,0),(0,0,0,1,1),(0,0,1,0,0),(0,0,1,1,1),
    (0,1,0,0,1),(0,1,0,1,0),(0,1,1,0,1),(0,1,1,1,0),
    (1,0,0,0,1),(1,0,0,1,0),(1,0,1,0,1),(1,0,1,1,0),
]

BC = [16, 32]
DEPTH = [4, 5]
ACT = ["sine", "cartoon"]
LR = [5e-4, 1e-3]
LOSS = ["masked_l1", "masked_l1_gradient"]

def build(rid, bc, depth, act, lr, loss):
    return {
        "experiment_id": f"cno_{rid:02d}",
        "strategy": "cno_ablation",
        "seed": 1, "epochs": 200, "lr": lr, "batch_size": 16,
        "checkpoint_interval": 50,
        "arch_name": "cno",
        "arch_kwargs": {"base_channels": bc, "depth": depth, "activation": act},
        "loss_name": loss, "loss_kwargs": {},
        "data_dir": f"{CRC}/shared/data",
        "results_dir": f"{CRC}/campaigns/{CAMP}/run_{rid:02d}",
        "split_manifest_path": f"{CRC}/shared/data/split_manifest.json",
        "heartbeat_interval_epochs": 50,
        "phase": "search", "eval_splits": ["val"], "compute_r2": True,
        "early_stop_wall_min": 100, "max_wall_min": 200,
        "baseline_r2_curve_path": f"{CRC}/shared/data/baseline_r2_curve.json",
    }

def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "campaigns", CAMP)
    for i, (b, d, a, lr_idx, lo) in enumerate(L12):
        cfg = build(i, BC[b], DEPTH[d], ACT[a], LR[lr_idx], LOSS[lo])
        d_ = os.path.join(out, f"run_{i:02d}"); os.makedirs(d_, exist_ok=True)
        json.dump(cfg, open(os.path.join(d_, "train_config.json"), "w"), indent=2)
    # Baseline: bc=32, depth=5, sine, l1_grad, 1e-3
    cfg = build(12, 32, 5, "sine", 1e-3, "masked_l1_gradient")
    d_ = os.path.join(out, "run_12"); os.makedirs(d_, exist_ok=True)
    json.dump(cfg, open(os.path.join(d_, "train_config.json"), "w"), indent=2)
    print(f"Wrote 13 configs to {out}")

if __name__ == "__main__":
    main()
