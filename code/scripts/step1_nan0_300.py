#!/usr/bin/env python3
"""
Train UNet on full dataset: NaN→0, building pixels Y=0 participate in loss.
Standard MAE loss (same as Lu), only NaN replaced with 0.
300 epochs trial run.
"""
from __future__ import annotations
import argparse, logging, random, time
from pathlib import Path
import numpy as np, torch
from torch.utils.data import DataLoader, TensorDataset
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "models"))
from unet_lu import UNetLu

ROOT = Path(__file__).resolve().parent.parent

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--epochs", type=int, default=300)
    p.add_argument("--lr", type=float, default=0.001)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--n-c", type=int, default=16)
    p.add_argument("--log-interval", type=int, default=10)
    p.add_argument("--num-workers", type=int, default=0)
    p.add_argument("--data-dir", type=Path, default=ROOT / "data/full_masked_640")
    p.add_argument("--results-dir", type=Path, default=ROOT / "results/full_nan0_640/seed_1")
    p.add_argument("--device", default=None)
    return p.parse_args()

def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))

    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    train_p = torch.load(args.data_dir / "train.pt", map_location="cpu", weights_only=False)
    test_p = torch.load(args.data_dir / "test.pt", map_location="cpu", weights_only=False)

    X_tr, Y_tr = train_p["X"], train_p["Y"]
    X_te, Y_te = test_p["X"], test_p["Y"]

    # NaN→0 for both X and Y (same as Lu)
    Y_tr = torch.nan_to_num(Y_tr, nan=0.0)
    Y_te = torch.nan_to_num(Y_te, nan=0.0)

    logging.info(f"Train: {X_tr.shape[0]} patches")
    logging.info(f"Test:  {X_te.shape[0]} patches")

    train_loader = DataLoader(TensorDataset(X_tr, Y_tr),
                              batch_size=args.batch_size, shuffle=True, num_workers=args.num_workers)
    test_loader = DataLoader(TensorDataset(X_te, Y_te),
                             batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers)

    model = UNetLu(n_c=args.n_c).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    criterion = torch.nn.L1Loss()  # Standard MAE, same as Lu
    logging.info(f"Params: {sum(p.numel() for p in model.parameters()):,}")
    logging.info(f"Loss: Standard MAE (L1), NaN→0, building Y=0 included")

    def run_epoch(loader, optimizer=None):
        model.train() if optimizer else model.eval()
        total_loss = 0.0
        with torch.set_grad_enabled(optimizer is not None):
            for batch in loader:
                x, y = [b.to(device) for b in batch]
                pred = model(x)
                loss = criterion(pred, y)
                if optimizer:
                    optimizer.zero_grad(set_to_none=True)
                    loss.backward()
                    optimizer.step()
                total_loss += loss.item() * x.size(0)
        return total_loss / len(loader.dataset)

    out = args.results_dir
    out.mkdir(parents=True, exist_ok=True)
    best_loss = float('inf')

    for epoch in range(1, args.epochs + 1):
        t0 = time.time()
        train_loss = run_epoch(train_loader, optimizer)
        test_loss = run_epoch(test_loader, None)
        if test_loss < best_loss:
            best_loss = test_loss
            torch.save(model.state_dict(), out / "model_best.pt")
        if epoch % args.log_interval == 0 or epoch == 1:
            dt = time.time() - t0
            logging.info(f"Epoch {epoch:4d}/{args.epochs}  train={train_loss:.6f}  test={test_loss:.6f}  best={best_loss:.6f}  {dt:.1f}s")

    torch.save(model.state_dict(), out / "model_final.pt")
    logging.info(f"Done. Best test loss: {best_loss:.6f}")

if __name__ == "__main__":
    main()
