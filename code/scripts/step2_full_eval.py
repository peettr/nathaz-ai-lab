#!/usr/bin/env python3
"""
Evaluate UNet on full dataset with masked loss approach.
Quick fix version.
"""
import argparse, json, logging, numpy as np, torch, re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "models"))
from unet_lu import UNetLu
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(__file__).resolve().parent.parent

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--n-c", type=int, default=16)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--data-dir", type=Path, default=ROOT / "data/full_masked_640")
    p.add_argument("--results-dir", type=Path, default=ROOT / "results/full_masked_640/seed_1")
    return p.parse_args()

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    args = parse_args()

    data = torch.load(args.data_dir / "test.pt", map_location="cpu", weights_only=False)
    X, Y, nan_mask = data["X"], data["Y"], data["nan_mask"]
    case_names = data["case_names"]
    patch_to_case = data["patch_to_case"]

    model = UNetLu(n_c=args.n_c).to(device)
    model.load_state_dict(torch.load(args.results_dir / "model_best.pt", map_location=device, weights_only=True))
    model.eval()

    loader = DataLoader(TensorDataset(X), batch_size=args.batch_size, shuffle=False)
    all_pred = []
    with torch.no_grad():
        for (x,) in loader:
            pred = model(x.to(device))
            all_pred.append(pred.cpu())
    pred_all = torch.cat(all_pred, dim=0)

    # Per-case metrics
    unique_cases = patch_to_case.unique()
    by_case = []
    all_gt, all_pr = [], []

    for ci in unique_cases:
        ci_val = ci.item()
        if ci_val >= len(case_names):
            continue
        mask = patch_to_case == ci
        idxs = mask.nonzero(as_tuple=True)[0]
        case_name = case_names[ci_val]

        gt_list, pr_list = [], []
        for idx in idxs:
            gt = Y[idx, 0].numpy()
            pr = pred_all[idx, 0].numpy()
            nm = nan_mask[idx, 0].numpy()
            bldg = X[idx, 0].numpy() > 0  # building = X > 0
            valid = np.isfinite(gt) & (~nm) & (~bldg)
            if valid.sum() > 0:
                gt_list.append(gt[valid])
                pr_list.append(pr[valid])

        if not gt_list:
            continue
        gt_flat = np.concatenate(gt_list)
        pr_flat = np.concatenate(pr_list)
        all_gt.append(gt_flat)
        all_pr.append(pr_flat)

        mae = float(np.mean(np.abs(gt_flat - pr_flat)))
        ss_res = float(np.sum((gt_flat - pr_flat) ** 2))
        ss_tot = float(np.sum((gt_flat - gt_flat.mean()) ** 2))
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        nmae = mae / np.mean(gt_flat) * 100 if np.mean(gt_flat) > 0 else 0.0

        by_case.append(dict(case_name=case_name, mae=float(mae), r2=float(r2), nmae=float(nmae),
                            u_mean=float(np.mean(gt_flat)), n_valid=int(len(gt_flat))))

    gt_all = np.concatenate(all_gt)
    pr_all = np.concatenate(all_pr)
    g_mae = float(np.mean(np.abs(gt_all - pr_all)))
    g_r2 = 1 - float(np.sum((gt_all - pr_all)**2)) / float(np.sum((gt_all - gt_all.mean())**2))
    g_nmae = g_mae / float(np.mean(gt_all)) * 100

    ideal = [c for c in by_case if c['case_name'].startswith(('VA','VS','UA','US'))]
    real = [c for c in by_case if not c['case_name'].startswith(('VA','VS','UA','US'))]

    result = dict(
        global_metrics=dict(mae=g_mae, r2=g_r2, nmae=g_nmae, n_total=len(by_case),
                           n_ideal=len(ideal), n_real=len(real)),
        idealized=dict(r2_median=float(np.median([c['r2'] for c in ideal])) if ideal else 0,
                       nmae_median=float(np.median([c['nmae'] for c in ideal])) if ideal else 0),
        realistic=dict(r2_median=float(np.median([c['r2'] for c in real])) if real else 0,
                       nmae_median=float(np.median([c['nmae'] for c in real])) if real else 0),
        by_case=by_case,
    )

    out_file = args.results_dir / "metrics_full.json"
    with open(out_file, 'w') as f:
        json.dump(result, f, indent=2)

    logging.info(f"Global: MAE={g_mae:.4f}, R2={g_r2:.4f}, NMAE={g_nmae:.1f}%")
    logging.info(f"MAE median={float(np.median([c['mae'] for c in by_case])):.4f}")
    logging.info(f"NMAE median={float(np.median([c['nmae'] for c in by_case])):.1f}%")
    if ideal:
        logging.info(f"Idealized ({len(ideal)}): R2={result['idealized']['r2_median']:.4f}, NMAE={result['idealized']['nmae_median']:.1f}%")
    if real:
        logging.info(f"Realistic ({len(real)}): R2={result['realistic']['r2_median']:.4f}, NMAE={result['realistic']['nmae_median']:.1f}%")
    logging.info(f"Saved to {out_file}")

if __name__ == "__main__":
    main()
