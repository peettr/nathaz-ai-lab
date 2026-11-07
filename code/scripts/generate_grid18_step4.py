#!/usr/bin/env python3
"""Generate Grid 18 Step 4 configs for ConvNeXt V2 UNet architecture search."""
import json
import os

CRC_PREFIX = "/groups/kareem/[用户]/graph-deeponet-wind/auto_v3"
CAMPAIGN_NAME = "grid18_step4"

L18 = [
    (0, 0, 0, 0), (0, 0, 1, 1), (0, 0, 2, 2),
    (0, 1, 0, 1), (0, 1, 1, 2), (0, 1, 2, 0),
    (0, 2, 0, 2), (0, 2, 1, 0), (0, 2, 2, 1),
    (1, 0, 0, 2), (1, 0, 1, 0), (1, 0, 2, 1),
    (1, 1, 0, 0), (1, 1, 1, 1), (1, 1, 2, 2),
    (1, 2, 0, 1), (1, 2, 1, 2), (1, 2, 2, 0),
]

LOSS_LEVELS = ["masked_l1", "masked_l1_gradient", "masked_huber"]
LR_LEVELS = [5e-4, 1e-3, 2e-3]
DEPTH_LEVELS = [4, 5]

SCHEDULER_LEVELS = [None, "cosine"]
WEIGHT_DECAY_LEVELS = [0, 1e-4]
GRAD_CLIP_LEVELS = [None, 0.5]
EMA_DECAY_LEVELS = [None, 0.999]
DATA_AUGMENT_LEVELS = [False, True]
NC_LEVELS = [16, 32]


def build_run(row_idx, row):
    depth_idx, _arch_idx, loss_idx, lr_idx = row
    depth = DEPTH_LEVELS[depth_idx]
    loss = LOSS_LEVELS[loss_idx]
    lr = LR_LEVELS[lr_idx]

    scheduler = SCHEDULER_LEVELS[(row_idx // 1) % 2]
    weight_decay = WEIGHT_DECAY_LEVELS[(row_idx // 2) % 2]
    grad_clip = GRAD_CLIP_LEVELS[(row_idx // 3) % 2]
    ema_decay = EMA_DECAY_LEVELS[(row_idx // 4) % 2]
    data_augment = DATA_AUGMENT_LEVELS[(row_idx // 5) % 2]
    n_c = NC_LEVELS[(row_idx // 6) % 2]

    # Ensure < 150M params
    if depth == 5 and n_c == 32:
        n_c = 16

    training = {
        "scheduler": scheduler,
        "weight_decay": weight_decay,
        "grad_clip": grad_clip,
        "ema_decay": ema_decay,
        "data_augment": data_augment,
    }

    return {
        "experiment_id": f"grid18_step4_{row_idx:02d}",
        "strategy": "grid18",
        "seed": 1,
        "epochs": 200,
        "lr": lr,
        "batch_size": 16,
        "checkpoint_interval": 50,
        "arch_name": "convnext_v2_unet",
        "arch_kwargs": {
            "n_c": n_c,
            "depth": depth,
            "training": training,
        },
        "loss_name": loss,
        "loss_kwargs": {},
        "data_dir": f"{CRC_PREFIX}/shared/data",
        "results_dir": f"{CRC_PREFIX}/campaigns/{CAMPAIGN_NAME}/run_{row_idx:02d}",
        "split_manifest_path": f"{CRC_PREFIX}/shared/data/split_manifest.json",
        "heartbeat_interval_epochs": 50,
        "phase": "search",
        "eval_splits": ["val"],
        "compute_r2": True,
        "early_stop_wall_min": 100,
        "max_wall_min": 200,
        "baseline_r2_curve_path": f"{CRC_PREFIX}/shared/data/baseline_r2_curve.json",
    }


def build_baseline():
    return {
        "experiment_id": "grid18_step4_baseline",
        "strategy": "grid18",
        "seed": 1,
        "epochs": 200,
        "lr": 1e-3,
        "batch_size": 16,
        "checkpoint_interval": 50,
        "arch_name": "convnext_v2_unet",
        "arch_kwargs": {
            "n_c": 16,
            "depth": 5,
            "training": {},
        },
        "loss_name": "masked_l1_gradient",
        "loss_kwargs": {},
        "data_dir": f"{CRC_PREFIX}/shared/data",
        "results_dir": f"{CRC_PREFIX}/campaigns/{CAMPAIGN_NAME}/baseline",
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
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "campaigns", CAMPAIGN_NAME)

    for row_idx, row in enumerate(L18):
        cfg = build_run(row_idx, row)
        run_dir = os.path.join(out_dir, f"run_{row_idx:02d}")
        os.makedirs(run_dir, exist_ok=True)
        with open(os.path.join(run_dir, "train_config.json"), "w") as f:
            json.dump(cfg, f, indent=2)

    bl = build_baseline()
    bl_dir = os.path.join(out_dir, "baseline")
    os.makedirs(bl_dir, exist_ok=True)
    with open(os.path.join(bl_dir, "train_config.json"), "w") as f:
        json.dump(bl, f, indent=2)

    print(f"Wrote 18 + 1 configs to {out_dir}")


if __name__ == "__main__":
    main()
