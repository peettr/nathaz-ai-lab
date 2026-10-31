#!/usr/bin/env python3
"""Generate SDF input feature ablation configs (8 runs)."""
import json
import os

CRC_PREFIX = "/groups/kareem/[用户]/graph-deeponet-wind/auto_v3"
CAMPAIGN_NAME = "step5_sdf"


def build_run(run_id, n_c, in_channels, input_features, loss, lr):
    return {
        "experiment_id": f"sdf_{run_id:02d}",
        "strategy": "sdf_ablation",
        "seed": 1,
        "epochs": 200,
        "lr": lr,
        "batch_size": 16,
        "checkpoint_interval": 50,
        "arch_name": "unet_v2_baseline",
        "arch_kwargs": {
            "n_c": n_c,
            "in_channels": in_channels,
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
        "input_features": input_features,
    }


def main():
    configs = [
        # Run 0: baseline replicate (1ch, same as step1 best config)
        (0, 32, 1, "height", "masked_l1", 1e-3),
        # Run 1: height + SDF (2ch)
        (1, 32, 2, "height_sdf", "masked_l1", 1e-3),
        # Run 2: height + SDF + normal (3ch)
        (2, 32, 3, "height_sdf_normal", "masked_l1", 1e-3),
        # Run 3: 3ch + l1_grad
        (3, 32, 3, "height_sdf_normal", "masked_l1_gradient", 1e-3),
        # Run 4: 3ch + lower lr
        (4, 32, 3, "height_sdf_normal", "masked_l1", 5e-4),
        # Run 5: 3ch + n_c=16 baseline + l1_grad
        (5, 16, 3, "height_sdf_normal", "masked_l1_gradient", 1e-3),
        # Run 6: 3ch + n_c=16 + l1
        (6, 16, 3, "height_sdf_normal", "masked_l1", 1e-3),
        # Run 7: 3ch + l1_grad + lower lr
        (7, 32, 3, "height_sdf_normal", "masked_l1_gradient", 5e-4),
    ]

    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "campaigns", CAMPAIGN_NAME,
    )

    for run_id, n_c, in_ch, feat, loss, lr in configs:
        cfg = build_run(run_id, n_c, in_ch, feat, loss, lr)
        run_dir = os.path.join(out_dir, f"run_{run_id:02d}")
        os.makedirs(run_dir, exist_ok=True)
        with open(os.path.join(run_dir, "train_config.json"), "w") as f:
            json.dump(cfg, f, indent=2)

    print(f"Wrote {len(configs)} configs to {out_dir}")


if __name__ == "__main__":
    main()
