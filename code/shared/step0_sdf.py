"""
step0_sdf.py — Build SDF-augmented train.pt / val.pt for auto_v3 pipeline.

Reads the existing idealized train/test split and raw topo files,
computes SDF + boundary normal channels, and saves as:
  data/lu_sdf_640/train.pt  — {"X": (N, 3, H, W), "Y": (N, 1, H, W)}
  data/lu_sdf_640/val.pt    — same format

Channel 0: building heights (from topo, flipud applied)
Channel 1: SDF (normalized to [-1, 1])
Channel 2: boundary normal angle (normalized to [0, 1])

Target: wind speed (sqrt(u²+v²) / 15.0), NaN → 0

Usage:
    python -m shared.step0_sdf \
        --split-dir scripts \
        --raw-dir data/urbantales/raw \
        --out-dir data/lu_sdf_640
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from shared.sdf import augment_input_channels


def load_topo(raw_dir: Path, case_name: str) -> np.ndarray:
    case_dir = raw_dir / case_name
    topo_files = list(case_dir.glob("*_topo"))
    if not topo_files:
        raise FileNotFoundError(f"No topo file in {case_dir}")
    topo = np.loadtxt(topo_files[0], dtype=np.float32)
    return np.flipud(topo)


def load_target(raw_dir: Path, case_name: str) -> np.ndarray:
    import xarray as xr
    case_dir = raw_dir / case_name
    ped_files = list(case_dir.glob("*_ped.nc"))
    if not ped_files:
        raise FileNotFoundError(f"No ped.nc in {case_dir}")
    ds = xr.open_dataset(ped_files[0])
    u = ds["uped"].values.astype(np.float32)
    v = ds["vped"].values.astype(np.float32)
    ds.close()
    speed = np.sqrt(u**2 + v**2)
    return speed


def build_split(
    case_list: list[str],
    raw_dir: Path,
) -> dict[str, torch.Tensor]:
    X_list = []
    Y_list = []
    for case in case_list:
        topo = load_topo(raw_dir, case)
        channels = augment_input_channels(topo)  # (3, H, W)
        target = load_target(raw_dir, case)       # (H, W)
        target = np.nan_to_num(target, nan=0.0) / 15.0
        X_list.append(channels)
        Y_list.append(target[np.newaxis])  # (1, H, W)

    X = torch.from_numpy(np.stack(X_list))  # (N, 3, H, W)
    Y = torch.from_numpy(np.stack(Y_list))  # (N, 1, H, W)
    return {"X": X, "Y": Y}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split-dir", type=Path, default=Path("scripts"))
    parser.add_argument("--train-split", default="lu_seed1_train.csv")
    parser.add_argument("--test-split", default="lu_seed1_test.csv")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/urbantales/raw"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/lu_sdf_640"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    train_cases = [l.strip() for l in open(args.split_dir / args.train_split) if l.strip()]
    test_cases = [l.strip() for l in open(args.split_dir / args.test_split) if l.strip()]
    print(f"Train: {len(train_cases)}, Val: {len(test_cases)}")

    print("Building train split...")
    train_data = build_split(train_cases, args.raw_dir)
    print(f"  X: {train_data['X'].shape}, Y: {train_data['Y'].shape}")

    print("Building val split...")
    val_data = build_split(test_cases, args.raw_dir)
    print(f"  X: {val_data['X'].shape}, Y: {val_data['Y'].shape}")

    torch.save(train_data, args.out_dir / "train.pt")
    torch.save(val_data, args.out_dir / "val.pt")
    print(f"Saved to {args.out_dir}/train.pt and val.pt")


if __name__ == "__main__":
    main()
