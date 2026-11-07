"""
Train UNet with circular padding on 640 masked data.
Same config as best run: 1000 epochs, batch=16, masked L1 loss.
"""
import os, sys, time, logging
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models.unet_lu_circular import UNetLuCircular

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

# Config
DATA_DIR = "data/full_masked_640"
RESULTS_DIR = "results/full_masked_640_circular/seed_1"
EPOCHS = 1000
BATCH_SIZE = 16
LR = 1e-3

os.makedirs(RESULTS_DIR, exist_ok=True)

# Load data
train_data = torch.load(f"{DATA_DIR}/train.pt", map_location="cpu", weights_only=False)
test_data = torch.load(f"{DATA_DIR}/test.pt", map_location="cpu", weights_only=False)
X_train, Y_train = train_data["X"], train_data["Y"]
X_test, Y_test = test_data["X"], test_data["Y"]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
X_train, Y_train = X_train.to(device), Y_train.to(device)
X_test, Y_test = X_test.to(device), Y_test.to(device)

# Masked L1 loss
nan_mask = torch.isnan(Y_train)
valid_mask = (~nan_mask) & (X_train <= 0)

nan_mask_test = torch.isnan(Y_test)
valid_mask_test = (~nan_mask_test) & (X_test <= 0)

def masked_l1(pred, target, mask):
    return torch.where(mask, (pred - target).abs(), torch.zeros_like(pred)).sum() / mask.sum().clamp(min=1)

# Model
model = UNetLuCircular(n_c=16).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)

train_loader = DataLoader(TensorDataset(X_train, Y_train), batch_size=BATCH_SIZE, shuffle=True)
best_test_loss = float('inf')

for epoch in range(1, EPOCHS + 1):
    model.train()
    train_loss_sum = 0
    n_batch = 0
    for xb, yb in train_loader:
        pred = model(xb)
        bm = (~torch.isnan(yb)) & (xb <= 0)
        loss = masked_l1(pred, yb, bm)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        train_loss_sum += loss.item()
        n_batch += 1
    train_loss = train_loss_sum / n_batch

    model.eval()
    with torch.no_grad():
        pred_test = model(X_test)
        test_loss = masked_l1(pred_test, Y_test, valid_mask_test).item()

    if test_loss < best_test_loss:
        best_test_loss = test_loss
        torch.save(model.state_dict(), f"{RESULTS_DIR}/model_best.pt")
        best_marker = " *"
    else:
        best_marker = ""

    if epoch % 10 == 0 or epoch == 1:
        logging.info(f"Epoch {epoch:4d}/{EPOCHS}  train={train_loss:.6f}  test={test_loss:.6f}  best={best_test_loss:.6f}{best_marker}")

torch.save(model.state_dict(), f"{RESULTS_DIR}/model_final.pt")
logging.info(f"Done. Best test loss: {best_test_loss:.6f}")
