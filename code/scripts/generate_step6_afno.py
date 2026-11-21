#!/usr/bin/env python3
"""Generate AFNO bottleneck experiment configs (10 runs)."""
import json
import os

CRC_PREFIX = "/groups/kareem/[用户]/graph-deeponet-wind/auto_v3"
CAMPAIGN_NAME = "step6_afno"

# L8 orthogonal table for 4 factors × 2 levels
L8 = [
    (0, 0, 0, 0), (0, 0, 1, 1), (0, 1, 0, 1), (0, 1, 1, 0),
    (1, 0, 0, 1), (1, 0, 1, 0), (1, 1, 0, 0), (1, 1, 1, 1),
]

AFNO_MODES = [16, 32]
AFNO_LAYERS = [1, 2]
LR = [5e-4, 1e-3]
LOSS = ["masked_l1", "masked_l1_gradient"]


def build_run(run_id, afno_modes, afno_layers, lr, loss):
    return {
        "experiment_id": f"afno_{run_id:02d}",
        "strategy": "afno_ablation",
        "seed": 1,
        "epochs": 200,
        "lr": lr,
        "batch_size": 16,
        "checkpoint_interval": 50,
        "arch_name": "unet_afno",
        "arch_kwargs": {
            "n_c": 32,
            "in_channels": 1,
            "afno_layers": afno_layers,
            "afno_modes": afno_modes,
            "depth": 5,
        },
        "loss_name": loss,
        "loss_kwargs": {},
        "data_dir": f"{CRC_PREFIX}/shared/data",
        "results_dir": f"{CRC_PREFIX}/campaigns/{CAMPAIGN_NAME}/run_{run_id:02d}",
        "split_manifest_path": f"{CRC_PREFIX}/shared/data/split_manifest.json",
        "heartbeat_interval_epochs": 50,
        "phase": "search",
        "eval_splits": ["val"],
        "compute_r2": True,
        "early_stop_wall_min": 100,
        "max_wall_min": 200,
        "baseline_r2_curve_path": f"{CRC_PREFIX}/shared/data/baseline_r2_curve.json",
    }


def main():
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "campaigns", CAMPAIGN_NAME,
    )

    # 8 runs from L8 orthogonal table
    for i, (m, l, lr_idx, loss_idx) in enumerate(L8):
        cfg = build_run(i, AFNO_MODES[m], AFNO_LAYERS[l], LR[lr_idx], LOSS[loss_idx])
        run_dir = os.path.join(out_dir, f"run_{i:02d}")
        os.makedirs(run_dir, exist_ok=True)
        with open(os.path.join(run_dir, "train_config.json"), "w") as f:
            json.dump(cfg, f, indent=2)

    # Run 8: baseline (no AFNO, same as UNet best config)
    cfg = build_run(8, 32, 0, 1e-3, "masked_l1")
    cfg["results_dir"] = f"{CRC_PREFIX}/campaigns/{CAMPAIGN_NAME}/run_08"
    run_dir = os.path.join(out_dir, "run_08")
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "train_config.json"), "w") as f:
        json.dump(cfg, f, indent=2)

    # Run 9: 64 modes + 2 layers (push limits)
    cfg = build_run(9, 64, 2, 5e-4, "masked_l1_gradient")
    cfg["results_dir"] = f"{CRC_PREFIX}/campaigns/{CAMPAIGN_NAME}/run_09"
    run_dir = os.path.join(out_dir, "run_09")
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "train_config.json"), "w") as f:
        json.dump(cfg, f, indent=2)

    print(f"Wrote 10 configs to {out_dir}")


if __name__ == "__main__":
    main()
