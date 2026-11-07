#!/usr/bin/env python3
"""Generate Swin-UNETR experiment configs (13 runs)."""
import json, os

CRC = "/groups/kareem/[用户]/graph-deeponet-wind/auto_v3"
CAMP = "step7_swin"

# L12 orthogonal table (5 factors × 2 levels, 12 runs)
L12 = [
    (0,0,0,0,0),(0,0,0,1,1),(0,0,1,0,0),(0,0,1,1,1),
    (0,1,0,0,1),(0,1,0,1,0),(0,1,1,0,1),(0,1,1,1,0),
    (1,0,0,0,1),(1,0,0,1,0),(1,0,1,0,1),(1,0,1,1,0),
]

EMBED = [48, 96]
WS = [8, 16]
LAYERS = [(2,2,2,2), (2,2,6,2)]
HEADS = [(3,6,12,24), (3,6,12,24)]  # same for both embed dims
LR = [5e-4, 1e-3]
LOSS = ["masked_l1", "masked_l1_gradient"]

def build(rid, embed, ws, layers, heads, lr, loss):
    return {
        "experiment_id": f"swin_{rid:02d}",
        "strategy": "swin_ablation",
        "seed": 1, "epochs": 200, "lr": lr, "batch_size": 16,
        "checkpoint_interval": 50,
        "arch_name": "swin_unetr",
        "arch_kwargs": {
            "embed_dim": embed, "window_size": ws,
            "num_layers": list(layers), "num_heads": list(heads),
        },
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
    for i, (e, w, l, lr_idx, lo) in enumerate(L12):
        cfg = build(i, EMBED[e], WS[w], LAYERS[l], HEADS[l], LR[lr_idx], LOSS[lo])
        d = os.path.join(out, f"run_{i:02d}"); os.makedirs(d, exist_ok=True)
        json.dump(cfg, open(os.path.join(d, "train_config.json"), "w"), indent=2)
    # Baseline: Swin-T default
    cfg = build(12, 96, 8, (2,2,6,2), (3,6,12,24), 1e-3, "masked_l1_gradient")
    d = os.path.join(out, "run_12"); os.makedirs(d, exist_ok=True)
    json.dump(cfg, open(os.path.join(d, "train_config.json"), "w"), indent=2)
    print(f"Wrote 13 configs to {out}")

if __name__ == "__main__":
    main()
