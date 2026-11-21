#!/usr/bin/env python3
"""Generate Grid 18 Step 3 configs for U-FNO architecture search."""
import json
import os

CRC_PREFIX = "/groups/kareem/[用户]/graph-deeponet-wind/auto_v3"
CAMPAIGN_NAME = "grid18_step3"

# L18 orthogonal array
L18 = [
    (0, 0, 0, 0), (0, 0, 1, 1), (0, 0, 2, 2),
    (0, 1, 0, 1), (0, 1, 1, 2), (0, 1, 2, 0),
    (0, 2, 0, 2), (0, 2, 1, 0), (0, 2, 2, 1),
    (1, 0, 0, 2), (1, 0, 1, 0), (1, 0, 2, 1),
    (1, 1, 0, 0), (1, 1, 1, 1), (1, 1, 2, 2),
    (1, 2, 0, 1), (1, 2, 1, 2), (1, 2, 2, 0),
]

# 3-level: Loss, lr
LOSS_LEVELS = ["masked_l1", "masked_l1_gradient", "masked_huber"]
LR_LEVELS = [5e-4, 1e-3, 2e-3]
# 2-level: depth via L18 col 0
# depth=4 (n_c=16→15M, n_c=32→60M), depth=5 (n_c=16→60M)
DEPTH_LEVELS = [4, 5]

# 2-level factors via divisors
SCHEDULER_LEVELS = [None, "cosine"]
WEIGHT_DECAY_LEVELS = [0, 1e-4]
GRAD_CLIP_LEVELS = [None, 0.5]
EMA_DECAY_LEVELS = [None, 0.999]
DATA_AUGMENT_LEVELS = [False, True]
NC_LEVELS = [16, 32]  # via divisor 6


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

    # Skip configs > 150M params
    params_est = n_c * (2 ** depth) * n_c * (2 ** depth) * 9  # rough
    if depth == 5 and n_c == 32:
        n_c = 16  # downgrade to stay under 150M

    modes = 32 if n_c >= 32 else 24

    training = {
        "scheduler": scheduler,
        "weight_decay": weight_decay,
        "grad_clip": grad_clip,
        "ema_decay": ema_decay,
        "data_augment": data_augment,
    }

    return {
        "experiment_id": f"grid18_step3_{row_idx:02d}",
        "strategy": "grid18",
        "seed": 1,
        "epochs": 200,
        "lr": lr,
        "batch_size": 16,
        "checkpoint_interval": 50,
        "arch_name": "ufno",
        "arch_kwargs": {
            "n_c": n_c,
            "depth": depth,
            "modes": modes,
            "fno_layers": 4,
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
        "experiment_id": "grid18_step3_baseline",
        "strategy": "grid18",
        "seed": 1,
        "epochs": 200,
        "lr": 1e-3,
        "batch_size": 16,
        "checkpoint_interval": 50,
        "arch_name": "ufno",
        "arch_kwargs": {
            "n_c": 32,
            "depth": 4,
            "modes": 32,
            "fno_layers": 4,
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
    import sys
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "campaigns", CAMPAIGN_NAME)

    print(f"{'#':>3}  {'n_c':>4}  {'depth':>5}  {'loss':<22}  {'lr':>7}  {'sched':<7}  {'wd':>6}  {'clip':>5}  {'ema':<6}  {'aug':<5}")
    print("-" * 95)

    for row_idx, row in enumerate(L18):
        cfg = build_run(row_idx, row)
        run_dir = os.path.join(out_dir, f"run_{row_idx:02d}")
        os.makedirs(run_dir, exist_ok=True)
        with open(os.path.join(run_dir, "train_config.json"), "w") as f:
            json.dump(cfg, f, indent=2)
        t = cfg["arch_kwargs"]["training"]
        print(f"{row_idx:>3}  {cfg['arch_kwargs']['n_c']:>4}  {cfg['arch_kwargs']['depth']:>5}  {cfg['loss_name']:<22}  {cfg['lr']:>7.0e}  {str(t['scheduler']):<7}  {t['weight_decay']:>6}  {str(t['grad_clip']):>5}  {str(t['ema_decay']):<6}  {str(t['data_augment']):<5}")

    bl = build_baseline()
    bl_dir = os.path.join(out_dir, "baseline")
    os.makedirs(bl_dir, exist_ok=True)
    with open(os.path.join(bl_dir, "train_config.json"), "w") as f:
        json.dump(bl, f, indent=2)
    print(f"\nbaseline: n_c=32 depth=4 modes=32 loss=masked_l1_gradient lr=1e-3")

    print(f"\nWrote 18 + 1 configs to {out_dir}")


if __name__ == "__main__":
    main()
