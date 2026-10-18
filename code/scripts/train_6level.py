"""
Train 6-level UNet (5 maxpool) on 640 masked data.
Masked L1 loss, 1000 epochs, Adam lr=1e-3.
Tries batch=8, falls back to 4 on OOM.
"""
import os, sys, logging
import torch
from torch.utils.data import DataLoader, TensorDataset
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models.unet_lu_6level import UNetLu6Level

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

DATA_DIR = "data/full_masked_640"
RESULTS_DIR = "results/full_masked_640_6level/seed_1"
EPOCHS = 1000
LR = 1e-3

os.makedirs(RESULTS_DIR, exist_ok=True)

train_data = torch.load(f"{DATA_DIR}/train.pt", map_location="cpu", weights_only=False)
test_data = torch.load(f"{DATA_DIR}/test.pt", map_location="cpu", weights_only=False)
X_train, Y_train = train_data["X"], train_data["Y"]
X_test, Y_test = test_data["X"], test_data["Y"]
del train_data, test_data

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
X_train, Y_train = X_train.to(device), Y_train.to(device)
X_test, Y_test = X_test.to(device), Y_test.to(device)

nan_mask_t = torch.isnan(Y_train)
valid_t = (~nan_mask_t) & (X_train <= 0)
nan_mask_e = torch.isnan(Y_test)
valid_e = (~nan_mask_e) & (X_test <= 0)

def masked_l1(pred, target, mask):
    return torch.where(mask, (pred - target).abs(), torch.zeros_like(pred)).sum() / mask.sum().clamp(min=1)

model = UNetLu6Level(n_c=16).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)

# Find working batch size
BATCH_SIZE = 8
for bs in [8, 4, 2]:
    try:
        test_pred = model(X_train[:bs])
        del test_pred
        torch.cuda.empty_cache()
        BATCH_SIZE = bs
        logging.info(f"Using batch_size={BATCH_SIZE}")
        break
    except RuntimeError as e:
        if "out of memory" in str(e):
            torch.cuda.empty_cache()
            continue
        raise

train_loader = DataLoader(TensorDataset(X_train, Y_train), batch_size=BATCH_SIZE, shuffle=True)
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

    model.eval()
    with torch.no_grad():
        pe = model(X_test)
        el = masked_l1(pe, Y_test, valid_e).item()

    if el < best_test_loss:
        best_test_loss = el
        torch.save(model.state_dict(), f"{RESULTS_DIR}/model_best.pt")
        mk = " *"
    else:
        mk = ""

    if epoch % 10 == 0 or epoch == 1:
        logging.info(f"Epoch {epoch:4d}/{EPOCHS}  train={tl:.6f}  test={el:.6f}  best={best_test_loss:.6f}{mk}")

torch.save(model.state_dict(), f"{RESULTS_DIR}/model_final.pt")
logging.info(f"Done. Best test loss: {best_test_loss:.6f}")
