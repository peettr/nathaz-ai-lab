"""
Train 7-level UNet (6 maxpool) on 640 masked data.
300 epochs, batched eval to avoid OOM.
"""
import os, sys, logging
import torch
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models.unet_lu_7level import UNetLu7Level

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

DATA_DIR = "data/full_masked_640"
RESULTS_DIR = "results/full_masked_640_7level/seed_1"
EPOCHS = 300
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

def masked_l1(pred, target, mask):
    return torch.where(mask, (pred - target).abs(), torch.zeros_like(pred)).sum() / mask.sum().clamp(min=1)

model = UNetLu7Level(n_c=16).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)

# Find working batch size for training
BATCH_SIZE = 8
for bs in [8, 4, 2, 1]:
    try:
        p = model(X_train[:bs])
        loss = masked_l1(p, Y_train[:bs], torch.ones_like(p[:,0], dtype=torch.bool))
        loss.backward()
        del p, loss
        torch.cuda.empty_cache()
        BATCH_SIZE = bs
        break
    except RuntimeError as e:
        if "out of memory" in str(e):
            torch.cuda.empty_cache()
            continue
        raise

# Find eval batch size (separate because test set might be larger)
EVAL_BS = 8
for bs in [8, 4, 2, 1]:
    try:
        p = model(X_test[:bs])
        del p
        torch.cuda.empty_cache()
        EVAL_BS = bs
        break
    except RuntimeError as e:
        if "out of memory" in str(e):
            torch.cuda.empty_cache()
            continue
        raise

logging.info(f"Train batch_size={BATCH_SIZE}, Eval batch_size={EVAL_BS}")

def batch_eval(model, X, Y, bs):
    model.eval()
    with torch.no_grad():
        preds = []
        for i in range(0, len(X), bs):
            preds.append(model(X[i:i+bs]))
        pred = torch.cat(preds, dim=0)
        valid = (~torch.isnan(Y)) & (X <= 0)
        return masked_l1(pred, Y, valid).item()

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
