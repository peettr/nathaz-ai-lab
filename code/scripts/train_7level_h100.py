"""
Train 7-level UNet (6 maxpool) on 640 masked data.
1000 epochs, batch=16, on H100 (80GB VRAM).
"""
import os, sys, logging
import torch
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models.unet_lu_7level import UNetLu7Level

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

DATA_DIR = "data/full_masked_640"
RESULTS_DIR = "results/full_masked_640_7level/seed_1"
EPOCHS = 1000
BATCH_SIZE = 16
LR = 1e-3

os.makedirs(RESULTS_DIR, exist_ok=True)

train_data = torch.load(f"{DATA_DIR}/train.pt", map_location="cpu", weights_only=False)
test_data = torch.load(f"{DATA_DIR}/test.pt", map_location="cpu", weights_only=False)
X_train, Y_train = train_data["X"], train_data["Y"]
X_test, Y_test = test_data["X"], test_data["Y"]
del train_data, test_data

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logging.info(f"Device: {device}")
X_train, Y_train = X_train.to(device), Y_train.to(device)
X_test, Y_test = X_test.to(device), Y_test.to(device)

valid_e = (~torch.isnan(Y_test)) & (X_test <= 0)

def masked_l1(pred, target, mask):
    return torch.where(mask, (pred - target).abs(), torch.zeros_like(pred)).sum() / mask.sum().clamp(min=1)

model = UNetLu7Level(n_c=16).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)

logging.info(f"Params: {sum(p.numel() for p in model.parameters()):,}")
logging.info(f"Batch size: {BATCH_SIZE}")

# Verify batch size works
try:
    p = model(X_train[:BATCH_SIZE])
    loss = masked_l1(p, Y_train[:BATCH_SIZE], (~torch.isnan(Y_train[:BATCH_SIZE])) & (X_train[:BATCH_SIZE] <= 0))
    loss.backward()
    del p, loss
    torch.cuda.empty_cache()
    logging.info(f"Batch {BATCH_SIZE} OK")
except RuntimeError as e:
    if "out of memory" in str(e):
        torch.cuda.empty_cache()
        BATCH_SIZE = 8
        logging.warning(f"OOM with 16, using batch={BATCH_SIZE}")

train_loader = DataLoader(TensorDataset(X_train, Y_train), batch_size=BATCH_SIZE, shuffle=True)

# Eval in batches to avoid OOM
EVAL_BS = 16
def batch_eval(model, X, Y, bs):
    model.eval()
    with torch.no_grad():
        preds = []
        for i in range(0, len(X), bs):
            preds.append(model(X[i:i+bs]))
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
        torch.save(model.state_dict(), f"{RESULTS_DIR}/model_best.pt")
        mk = " *"
    else:
        mk = ""

    if epoch % 10 == 0 or epoch == 1:
        logging.info(f"Epoch {epoch:4d}/{EPOCHS}  train={tl:.6f}  test={el:.6f}  best={best_test_loss:.6f}{mk}")

torch.save(model.state_dict(), f"{RESULTS_DIR}/model_final.pt")
logging.info(f"Done. Best test loss: {best_test_loss:.6f}")
