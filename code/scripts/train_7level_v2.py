"""
Train 7-level UNet for a given seed, using Lu's exact train/test split.
Split from metrics_in_training_set_seedN.csv + metrics_in_test_set_seedN.csv.
Supports checkpoint save/resume every 100 epochs.
Usage: python train_7level_v2.py --seed N
"""
import os, sys, argparse, logging
import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models.unet_lu_7level import UNetLu7Level

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
parser = argparse.ArgumentParser()
parser.add_argument('--seed', type=int, required=True)
args = parser.parse_args()

SEED = args.seed
EPOCHS = 1000
BATCH_SIZE = 16
LR = 1e-3
CKPT_INTERVAL = 100

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FMT_DIR = os.path.join(ROOT, "data", "full_masked_640")
RESULTS_DIR = os.path.join(ROOT, "results", "full_masked_640_7level", f"seed_{SEED}")
os.makedirs(RESULTS_DIR, exist_ok=True)

CKPT_PATH = os.path.join(RESULTS_DIR, "checkpoint.pt")

# ---- Load Lu's split for this seed ----
lu_train_csv = os.path.join(ROOT, "references", "all_cases_20exp", f"metrics_in_training_set_seed{SEED}.csv")
lu_test_csv = os.path.join(ROOT, "references", "all_cases_20exp", f"metrics_in_test_set_seed{SEED}.csv")

lu_train = pd.read_csv(lu_train_csv)
lu_test = pd.read_csv(lu_test_csv)

# Build case_name: topo_d{angle:02d}, exclude 'total' (global pooled metric, not a real case)
lu_train = lu_train[lu_train['topo'] != 'total']
lu_test = lu_test[lu_test['topo'] != 'total']
train_cases_lu = set(lu_train['topo'].astype(str) + '_d' + lu_train['angle'].astype(str).str.zfill(2))
test_cases_lu = set(lu_test['topo'].astype(str) + '_d' + lu_test['angle'].astype(str).str.zfill(2))

logging.info(f"Seed {SEED}: Lu train={len(train_cases_lu)}, test={len(test_cases_lu)}")
assert len(train_cases_lu & test_cases_lu) == 0, "Train/test overlap!"

all_cases_lu = train_cases_lu | test_cases_lu
logging.info(f"Total unique cases from Lu: {len(all_cases_lu)}")

# ---- Load all formatted data (merged train+test from seed 1) ----
train_pt = torch.load(os.path.join(FMT_DIR, "train.pt"), map_location="cpu", weights_only=False)
test_pt = torch.load(os.path.join(FMT_DIR, "test.pt"), map_location="cpu", weights_only=False)
X_all = torch.cat([train_pt["X"], test_pt["X"]], dim=0)
Y_all = torch.cat([train_pt["Y"], test_pt["Y"]], dim=0)
del train_pt, test_pt

# ---- Build case_name -> patch indices mapping ----
train_csv = os.path.join(ROOT, "scripts", "lu_full_train_seed1.csv")
test_csv = os.path.join(ROOT, "scripts", "lu_full_test_seed1.csv")
train_df = pd.read_csv(train_csv)
test_df = pd.read_csv(test_csv)
all_df = pd.concat([train_df, test_df], ignore_index=True)

case_to_indices = {}
for idx, row in all_df.iterrows():
    cn = row['case_name']
    if cn not in case_to_indices:
        case_to_indices[cn] = []
    case_to_indices[cn].append(idx)

our_cases = set(case_to_indices.keys())
logging.info(f"Our formatted data: {len(our_cases)} cases, {len(all_df)} patches")

# ---- Check coverage ----
matched = all_cases_lu & our_cases
unmatched_lu = all_cases_lu - our_cases
unmatched_ours = our_cases - all_cases_lu

if unmatched_lu:
    logging.warning(f"Lu cases not in our data ({len(unmatched_lu)}): {sorted(unmatched_lu)[:10]}")
if unmatched_ours:
    logging.info(f"Our cases not in Lu ({len(unmatched_ours)}): {sorted(unmatched_ours)[:10]}")
logging.info(f"Matched cases: {len(matched)}/{len(all_cases_lu)}")

# ---- Split by Lu's train/test ----
train_patch_idx = []
test_patch_idx = []

for c in sorted(case_to_indices.keys()):
    if c in test_cases_lu:
        test_patch_idx.extend(case_to_indices[c])
    elif c in train_cases_lu:
        train_patch_idx.extend(case_to_indices[c])
    # else: not in Lu's split for this seed, skip

logging.info(f"Train: {len(train_patch_idx)} patches, Test: {len(test_patch_idx)} patches")

X_train = X_all[train_patch_idx].clone()
Y_train = Y_all[train_patch_idx].clone()
X_test = X_all[test_patch_idx].clone()
Y_test = Y_all[test_patch_idx].clone()
del X_all, Y_all

# ---- Training setup ----
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
gpu_name = torch.cuda.get_device_name(device) if torch.cuda.is_available() else "CPU"
logging.info(f"Device: {device}, GPU: {gpu_name}")

X_train, Y_train = X_train.to(device), Y_train.to(device)
X_test, Y_test = X_test.to(device), Y_test.to(device)

def masked_l1(pred, target, mask):
    return torch.where(mask, (pred - target).abs(), torch.zeros_like(pred)).sum() / mask.sum().clamp(min=1)

model = UNetLu7Level(n_c=16).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)
logging.info(f"Params: {sum(p.numel() for p in model.parameters()):,}")

# ---- Resume from checkpoint if exists ----
start_epoch = 1
best_test_loss = float('inf')

if os.path.exists(CKPT_PATH):
    ckpt = torch.load(CKPT_PATH, map_location=device, weights_only=False)
    model.load_state_dict(ckpt['model_state_dict'])
    optimizer.load_state_dict(ckpt['optimizer_state_dict'])
    start_epoch = ckpt['epoch'] + 1
    best_test_loss = ckpt['best_test_loss']
    logging.info(f"Resumed from epoch {ckpt['epoch']}, best_test_loss={best_test_loss:.6f}")
    # Also restore model_best if it was saved
    best_path = os.path.join(RESULTS_DIR, "model_best.pt")
    if os.path.exists(best_path):
        logging.info("model_best.pt exists, will be preserved")

# Verify batch size
try:
    p = model(X_train[:BATCH_SIZE])
    bm = (~torch.isnan(Y_train[:BATCH_SIZE])) & (X_train[:BATCH_SIZE] <= 0)
    loss = masked_l1(p, Y_train[:BATCH_SIZE], bm)
    loss.backward()
    del p, loss
    torch.cuda.empty_cache()
    logging.info(f"Batch {BATCH_SIZE} OK")
except RuntimeError:
    torch.cuda.empty_cache()
    BATCH_SIZE = 8
    logging.warning(f"OOM with 16, using batch={BATCH_SIZE}")

train_loader = DataLoader(TensorDataset(X_train, Y_train), batch_size=BATCH_SIZE, shuffle=True)

EVAL_BS = 16
def batch_eval(model, X, Y, bs):
    model.eval()
    with torch.no_grad():
        preds = [model(X[i:i+bs]) for i in range(0, len(X), bs)]
        pred = torch.cat(preds, dim=0)
        valid = (~torch.isnan(Y)) & (X <= 0)
        return masked_l1(pred, Y, valid).item()

for epoch in range(start_epoch, EPOCHS + 1):
    model.train()
    tot = 0.0; n = 0
    for xb, yb in train_loader:
        pred = model(xb)
        bm = (~torch.isnan(yb)) & (xb <= 0)
        loss = masked_l1(pred, yb, bm)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        tot += loss.item(); n += 1
    tl = tot / n

    el = batch_eval(model, X_test, Y_test, EVAL_BS)

    if el < best_test_loss:
        best_test_loss = el
        torch.save(model.state_dict(), os.path.join(RESULTS_DIR, "model_best.pt"))

    if epoch % 10 == 0 or epoch == 1:
        mk = " *" if el <= best_test_loss else ""
        logging.info(f"Epoch {epoch:4d}/{EPOCHS}  train={tl:.6f}  test={el:.6f}  best={best_test_loss:.6f}{mk}")

    # ---- Checkpoint every CKPT_INTERVAL epochs ----
    if epoch % CKPT_INTERVAL == 0:
        torch.save({
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'best_test_loss': best_test_loss,
            'seed': SEED,
        }, CKPT_PATH)
        logging.info(f"Checkpoint saved at epoch {epoch}")

torch.save(model.state_dict(), os.path.join(RESULTS_DIR, "model_final.pt"))
# Clean up checkpoint on successful completion
if os.path.exists(CKPT_PATH):
    os.remove(CKPT_PATH)
logging.info(f"Seed {SEED} done. Best test loss: {best_test_loss:.6f}")
