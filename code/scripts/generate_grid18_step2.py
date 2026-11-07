#!/usr/bin/env python3
"""Generate Grid 18 Step 2 configs for F-FNO architecture search.

Uses the same L18 + divisor pattern as generate_grid18.py but with F-FNO hyperparams.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AUTO_V3 = os.path.dirname(HERE)

# L18 orthogonal array (same as Stage 1)
L18 = [
    (0, 0, 0, 0),
    (0, 0, 1, 1),
    (0, 0, 2, 2),
    (0, 1, 0, 1),
    (0, 1, 1, 2),
    (0, 1, 2, 0),
    (0, 2, 0, 2),
    (0, 2, 1, 0),
    (0, 2, 2, 1),
    (1, 0, 0, 2),
    (1, 0, 1, 0),
    (1, 0, 2, 1),
    (1, 1, 0, 0),
    (1, 1, 1, 1),
    (1, 1, 2, 2),
    (1, 2, 0, 1),
    (1, 2, 1, 2),
    (1, 2, 2, 0),
]

CRC_PREFIX = "/groups/kareem/[用户]/graph-deeponet-wind/auto_v3"
CAMPAIGN_NAME = "grid18_step2"

# 3-level factors
LOSS_LEVELS = ["masked_l1", "masked_l1_gradient", "masked_huber"]
LR_LEVELS = [5e-4, 1e-3, 2e-3]
# 2-level factors (n_c via L18 column 0)
NC_LEVELS = [16, 32]

# 6 two-level factors via divisors
SCHEDULER_LEVELS = [None, "cosine"]
WEIGHT_DECAY_LEVELS = [0, 1e-4]
GRAD_CLIP_LEVELS = [None, 0.5]
EMA_DECAY_LEVELS = [None, 0.999]
DATA_AUGMENT_LEVELS = [False, True]
# F-FNO specific: n_layers
NLAYERS_LEVELS = [3, 5]


def _fmt_lr(lr: float) -> str:
    return f"{lr:.0e}".replace("e-0", "e-").replace("e+0", "e+")


def build_run(row_idx, row):
    nc_idx, _arch_idx, loss_idx, lr_idx = row
    n_c = NC_LEVELS[nc_idx]
    loss = LOSS_LEVELS[loss_idx]
    lr = LR_LEVELS[lr_idx]

    # Divisor-based 2-level assignment (same as Stage 1)
    scheduler = SCHEDULER_LEVELS[(row_idx // 1) % 2]
    weight_decay = WEIGHT_DECAY_LEVELS[(row_idx // 2) % 2]
    grad_clip = GRAD_CLIP_LEVELS[(row_idx // 3) % 2]
    ema_decay = EMA_DECAY_LEVELS[(row_idx // 4) % 2]
    data_augment = DATA_AUGMENT_LEVELS[(row_idx // 5) % 2]
    n_layers = NLAYERS_LEVELS[(row_idx // 6) % 2]

    # F-FNO modes: scale with n_c
    modes = 32 if n_c >= 32 else 24

    training = {
        "scheduler": scheduler,
        "weight_decay": weight_decay,
        "grad_clip": grad_clip,
        "ema_decay": ema_decay,
        "data_augment": data_augment,
    }

    return {
        "experiment_id": f"grid18_step2_{row_idx:02d}",
        "strategy": "grid18",
        "seed": 1,
        "epochs": 200,
        "lr": lr,
        "batch_size": 16,
        "checkpoint_interval": 50,
        "arch_name": "ffno",
        "arch_kwargs": {
            "n_c": n_c,
            "n_layers": n_layers,
            "modes": modes,
            "activation": "gelu",
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
    }


def build_baseline():
    return {
        "experiment_id": "grid18_step2_baseline",
        "strategy": "grid18",
        "seed": 1,
        "epochs": 200,
        "lr": 1e-3,
        "batch_size": 16,
        "checkpoint_interval": 50,
        "arch_name": "ffno",
        "arch_kwargs": {
            "n_c": 32,
            "n_layers": 4,
            "modes": 32,
            "activation": "gelu",
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
    }


def main():
    campaign_dir = os.path.join(AUTO_V3, "campaigns", CAMPAIGN_NAME)
    os.makedirs(campaign_dir, exist_ok=True)

    header = (
        f"{'#':>3}  {'n_c':>4}  {'loss':<22}  {'lr':>7}  "
        f"{'sched':<7}  {'wd':>6}  {'clip':>5}  "
        f"{'ema':<6}  {'aug':<5}  {'layers':>7}"
    )
    print(header)
    print("-" * len(header))

    for row_idx, row in enumerate(L18):
        cfg = build_run(row_idx, row)
        run_dir = os.path.join(campaign_dir, f"run_{row_idx:02d}")
        os.makedirs(run_dir, exist_ok=True)
        with open(os.path.join(run_dir, "train_config.json"), "w") as f:
            json.dump(cfg, f, indent=2)

        t = cfg["arch_kwargs"]["training"]
        print(
            f"{row_idx:>3}  {cfg['arch_kwargs']['n_c']:>4}  {cfg['loss_name']:<22}  "
            f"{cfg['lr']:>7.0e}  {str(t['scheduler']):<7}  "
            f"{t['weight_decay']:>6}  {str(t['grad_clip']):>5}  "
            f"{str(t['ema_decay']):<6}  {str(t['data_augment']):<5}  "
            f"{cfg['arch_kwargs']['n_layers']:>7}"
        )

    # Baseline
    bl = build_baseline()
    bl_dir = os.path.join(campaign_dir, "baseline")
    os.makedirs(bl_dir, exist_ok=True)
    with open(os.path.join(bl_dir, "train_config.json"), "w") as f:
        json.dump(bl, f, indent=2)
    print(f"\nbaseline: n_c=32 layers=4 modes=32 loss=masked_l1_gradient lr=1e-3")

    print(f"\nWrote 18 + 1 configs to {campaign_dir}")


if __name__ == "__main__":
    main()
