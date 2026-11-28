"""
Train 7-level UNet on 640 masked data for a given seed (1-20).
Usage: python train_7level_seed.py --seed N
Follows Lu's exact split method: np.random.seed(N), shuffle, 80/20.
"""
import os, sys, argparse, logging
import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

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
FMT_SHAPE = 640
TRAIN_RATIO = 0.8

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FMT_DIR = os.path.join(ROOT, "data", "full_masked_640")
RESULTS_DIR = os.path.join(ROOT, "results", "full_masked_640_7level", f"seed_{SEED}")
os.makedirs(RESULTS_DIR, exist_ok=True)

# Load ALL formatted data (train.pt + test.pt merged = all)
# We need to re-split by seed using Lu's method
train_pt = torch.load(os.path.join(FMT_DIR, "train.pt"), map_location="cpu", weights_only=False)
test_pt = torch.load(os.path.join(FMT_DIR, "test.pt"), map_location="cpu", weights_only=False)

# But actually we need to split from raw data level. The formatted data already
# has patches from multiple cases. We need to split by CASE (raw_data index).
# Load the case mapping
import pandas as pd
# The test CSV has case_name and patch indices for seed 1
# We need to generate splits for arbitrary seed using Lu's method

# Alternative: use the full formatted dataset and split by case
# Load all data
X_all = torch.cat([train_pt["X"], test_pt["X"]], dim=0)
Y_all = torch.cat([train_pt["Y"], test_pt["Y"]], dim=0)

# Load case-to-patch mapping
test_csv = os.path.join(ROOT, "scripts", "lu_full_test_seed1.csv")
train_csv = os.path.join(ROOT, "scripts", "lu_full_train_seed1.csv")

# We have 512 cases total, each expanded to patches
# Need to regenerate per-seed splits
# Lu's method: shuffle case indices, 80% train, 20% test
# Total cases = 512 (224 ideal + 288 realistic for full dataset)
# Actually, let's figure out the exact number of cases

# Read Lu's reference to get case list
ref_dir = os.path.join(ROOT, "references", "all_cases_20exp")
# Get unique case names from Lu's seed 1 test set
lu_test1 = pd.read_csv(os.path.join(ref_dir, "metrics_in_test_set_seed1.csv"))
lu_test2 = pd.read_csv(os.path.join(ref_dir, "metrics_in_test_set_seed2.csv"))

# Check if case lists differ between seeds
cases1 = set(zip(lu_test1['topo'], lu_test1['angle']))
cases2 = set(zip(lu_test2['topo'], lu_test2['angle']))
logging.info(f"Seed 1 test cases: {len(cases1)}, Seed 2 test cases: {len(cases2)}")
logging.info(f"Overlap: {len(cases1 & cases2)}")

# Lu uses ALL 512 cases with 80/20 split per seed
# We need to replicate this. First, build the full case list.
import glob

# Get all raw data cases
raw_dir = os.path.join(ROOT, "data", "full_masked_640")
# Actually, the formatted data was built from all cases already
# The patches in train.pt + test.pt = all patches from all cases

# Simpler approach: use DataFormatter to split like Lu does
sys.path.insert(0, os.path.join(ROOT, "references"))
from data_formatter import DataFormatter, DEFAULT_FORMAT_SHAPE

# Load raw data
raw_data_dir = os.path.join(ROOT, "..", "..", "data", "urbantales", "raw")
# Check what raw data looks like
import pickle
# Lu loads raw_data from pickle files

# Actually, the simplest correct approach:
# 1. Load the case list (512 cases)
# 2. For each seed, shuffle and split 80/20
# 3. Load formatted patches for train/test cases
# 4. Train

# Let's build case list from the formatted data we already have
# Read the original split CSVs to get case names
train_df1 = pd.read_csv(train_csv)
test_df1 = pd.read_csv(test_csv)
all_cases = sorted(set(train_df1['case_name'].tolist() + test_df1['case_name'].tolist()))
logging.info(f"Total cases: {len(all_cases)}")

# Build case_name -> patch_indices mapping
all_df = pd.concat([train_df1, test_df1], ignore_index=True)
case_to_indices = {}
for idx, row in all_df.iterrows():
    cn = row['case_name']
    if cn not in case_to_indices:
        case_to_indices[cn] = []
    case_to_indices[cn].append(idx)

# Now split like Lu: np.random.seed(SEED), shuffle case indices, 80/20
n_cases = len(all_cases)
n_train = round(TRAIN_RATIO * n_cases)
np.random.seed(SEED)
shuffled = list(range(n_cases))
np.random.shuffle(shuffled)
train_case_idx = sorted(shuffled[:n_train])
test_case_idx = sorted(shuffled[n_train:])

train_cases = [all_cases[i] for i in train_case_idx]
test_cases = [all_cases[i] for i in test_case_idx]

# Collect patch indices
train_patch_idx = []
for c in train_cases:
    train_patch_idx.extend(case_to_indices[c])
test_patch_idx = []
for c in test_cases:
    test_patch_idx.extend(case_to_indices[c])

logging.info(f"Seed {SEED}: {len(train_cases)} train cases ({len(train_patch_idx)} patches), "
             f"{len(test_cases)} test cases ({len(test_patch_idx)} patches)")

# Split data
X_train = X_all[train_patch_idx]
Y_train = Y_all[train_patch_idx]
X_test = X_all[test_patch_idx]
Y_test = Y_all[test_patch_idx]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logging.info(f"Device: {device}, GPU: {torch.cuda.get_device_name() if torch.cuda.is_available() else 'CPU'}")

# Free full dataset early to save VRAM
del X_all, Y_all, train_pt, test_pt

X_train, Y_train = X_train.to(device), Y_train.to(device)
X_test, Y_test = X_test.to(device), Y_test.to(device)

valid_e = (~torch.isnan(Y_test)) & (X_test <= 0)

def masked_l1(pred, target, mask):
    return torch.where(mask, (pred - target).abs(), torch.zeros_like(pred)).sum() / mask.sum().clamp(min=1)

model = UNetLu7Level(n_c=16).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)

logging.info(f"Params: {sum(p.numel() for p in model.parameters()):,}, Batch: {BATCH_SIZE}")

# Verify batch size
try:
    p = model(X_train[:BATCH_SIZE])
    loss = masked_l1(p, Y_train[:BATCH_SIZE], (~torch.isnan(Y_train[:BATCH_SIZE])) & (X_train[:BATCH_SIZE] <= 0))
    loss.backward()
    del p, loss
    torch.cuda.empty_cache()
except RuntimeError:
    torch.cuda.empty_cache()
    BATCH_SIZE = 8
    logging.warning(f"OOM, using batch={BATCH_SIZE}")

train_loader = DataLoader(TensorDataset(X_train, Y_train), batch_size=BATCH_SIZE, shuffle=True)

EVAL_BS = 16
def batch_eval(model, X, Y, bs):
    model.eval()
    with torch.no_grad():
        preds = [model(X[i:i+bs]) for i in range(0, len(X), bs)]
        pred = torch.cat(preds, dim=0)
        valid = (~torch.isnan(Y)) & (X <= 0)
        return masked_l1(pred, Y, valid).item()

best_test_loss = float('inf')

for epoch in range(1, EPOCHS + 1):
    model.train()
    tot = 0.0
    n = 0
    for xb, yb in train_loader:
        pred = model(xb)
        bm = (~torch.isnan(yb)) & (xb <= 0)
        loss = masked_l1(pred, yb, bm)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        tot += loss.item()
        n += 1
    tl = tot / n

    el = batch_eval(model, X_test, Y_test, EVAL_BS)

    if el < best_test_loss:
        best_test_loss = el
        torch.save(model.state_dict(), os.path.join(RESULTS_DIR, "model_best.pt"))

    if epoch % 10 == 0 or epoch == 1:
        mk = " *" if el <= best_test_loss else ""
        logging.info(f"Epoch {epoch:4d}/{EPOCHS}  train={tl:.6f}  test={el:.6f}  best={best_test_loss:.6f}{mk}")

torch.save(model.state_dict(), os.path.join(RESULTS_DIR, "model_final.pt"))
logging.info(f"Seed {SEED} done. Best test loss: {best_test_loss:.6f}")
