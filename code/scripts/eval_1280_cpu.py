#!/usr/bin/env python3
"""
Evaluate current 1280 training checkpoint on CPU to avoid OOM.
"""
import json, logging, numpy as np, torch, re, sys
from pathlib import Path
import pandas as pd, xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent / "models"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "references"))
from unet_lu import UNetLu
from data_formatter_fixed import DataFormatterFixed as DataFormatter

ROOT = Path('/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset')
RAW_DIR = Path('/groups/kareem/[用户]/graph-deeponet-wind/data/urbantales/raw')

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

# Load test data
data = torch.load(ROOT / 'data/full_masked_1280/test.pt', map_location='cpu', weights_only=False)
X, Y = data["X"], data["Y"]

# Load model on CPU
model = UNetLu(n_c=16)
model.load_state_dict(torch.load(ROOT / 'results/full_masked_1280/seed_1/model_best.pt', map_location='cpu', weights_only=True))
model.eval()
logging.info("Loaded model_best.pt on CPU")

# Inference batch by batch on CPU
from torch.utils.data import DataLoader, TensorDataset
loader = DataLoader(TensorDataset(X), batch_size=4, shuffle=False)
all_pred = []
with torch.no_grad():
    for (x,) in loader:
        all_pred.append(model(x))
pred_all = torch.cat(all_pred, dim=0)
pred_np = np.nan_to_num(pred_all.numpy()[:, 0, :, :], nan=0.0).astype(np.float32)
logging.info(f"Inference done: {pred_np.shape}")

# Rebuild formatter
test_df = pd.read_csv(ROOT / 'scripts/lu_full_test_seed1.csv')
test_cases_list = sorted(test_df['case_name'].tolist())

raw_data_list, wind_angle_list, loaded_names = [], [], []
for cn in test_cases_list:
    case_dir = RAW_DIR / cn
    if not case_dir.is_dir(): continue
    try:
        topo = np.flipud(np.loadtxt(case_dir / f"{cn}_topo", dtype=np.float32))
        with xr.open_dataset(case_dir / f"{cn}_ped.nc") as ds:
            Uped = ds["Uped"].values.astype(np.float32)
        combined = Uped.copy()
        combined[topo > 0] = -topo[topo > 0]
        m = re.search(r"_d(\d+)$", cn)
        raw_data_list.append(combined)
        wind_angle_list.append(int(m.group(1)))
        loaded_names.append(cn)
    except: pass

formatter = DataFormatter(raw_data=raw_data_list, wind_angles=wind_angle_list, formatted_shape=1280)
pred_formatted = pred_np[:, np.newaxis, :, :]
restored = formatter.restore_raw_output_data(pred_formatted)

# Compute metrics
by_case = []
all_gt, all_pr = [], []
for i, cn in enumerate(loaded_names):
    truth = raw_data_list[i]
    pred = restored[i]
    if truth.shape != pred.shape:
        if truth.shape == pred.T.shape:
            pred = pred.T
        else:
            continue
    valid = truth >= 0
    valid = valid & np.isfinite(truth) & np.isfinite(pred)
    t = truth[valid]
    p = pred[valid]
    if len(t) == 0: continue
    all_gt.append(t); all_pr.append(p)
    mae = float(np.mean(np.abs(t - p)))
    ss_res = float(np.sum((t - p)**2))
    ss_tot = float(np.sum((t - t.mean())**2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    nmae = mae / np.mean(t) * 100 if np.mean(t) > 0 else 0.0
    by_case.append(dict(case_name=cn, mae=mae, r2=float(r2), nmae=float(nmae),
                        u_mean=float(np.mean(t)), n_valid=int(len(t)),
                        category='idealized' if cn.startswith(('VA','VS','UA','US')) else 'realistic'))

gt_all = np.concatenate(all_gt)
pr_all = np.concatenate(all_pr)
g_mae = float(np.mean(np.abs(gt_all - pr_all)))
g_r2 = 1 - float(np.sum((gt_all - pr_all)**2)) / float(np.sum((gt_all - gt_all.mean())**2))

ideal = [c for c in by_case if c['category'] == 'idealized']
real = [c for c in by_case if c['category'] == 'realistic']

print(f"\n=== 1280 Current Best (raw-domain, CPU eval) ===")
print(f"Global: MAE={g_mae:.4f}, R2={g_r2:.4f}")
print(f"Idealized ({len(ideal)}): R2_median={np.median([c['r2'] for c in ideal]):.4f}, NMAE_median={np.median([c['nmae'] for c in ideal]):.1f}%")
print(f"Realistic ({len(real)}): R2_median={np.median([c['r2'] for c in real]):.4f}, NMAE_median={np.median([c['nmae'] for c in real]):.1f}%")

# Compare with 640
with open(ROOT / 'results/full_masked_640/seed_1/metrics_raw_restore_best.json') as f:
    m640 = json.load(f)

print(f"\n--- vs 640 masked ---")
print(f"{'Metric':<20} {'1280':>10} {'640':>10}")
print(f"{'Global R2':<20} {g_r2:10.4f} {m640['global_metrics']['r2']:10.4f}")
print(f"{'Ideal R2 median':<20} {np.median([c['r2'] for c in ideal]):10.4f} {m640['idealized']['r2_median']:10.4f}")
print(f"{'Real R2 median':<20} {np.median([c['r2'] for c in real]):10.4f} {m640['realistic']['r2_median']:10.4f}")
