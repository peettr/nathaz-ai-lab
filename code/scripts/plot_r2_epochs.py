#!/usr/bin/env python3
"""Plot R² vs epoch from training logs for top3_1k runs."""
import re, os, glob
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = "/groups/kareem/[用户]/graph-deeponet-wind/auto_v3"
DIR = f"{BASE}/campaigns/grid18_top3_1k"

runs = {
    "baseline (L1, n_c=16)": "baseline",
    "run_02 (Huber, n_c=16, lr=2e-3)": "run_02",
    "run_11 (Huber, n_c=32, lr=1e-3)": "run_11",
    "run_17 (Huber, n_c=32, lr=5e-4)": "run_17",
}

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

for label, name in runs.items():
    log_path = f"{DIR}/{name}.out"
    if not os.path.exists(log_path):
        continue
    
    with open(log_path) as f:
        lines = f.readlines()
    
    epochs, r2s, val_losses = [], [], []
    for line in lines:
        m = re.search(r'Epoch\s+(\d+)/\d+\s+train=[\d.]+\s+val=([\d.]+)\s+best=[\d.]+\s+R²=([-\d.]+)', line)
        if m:
            epochs.append(int(m.group(1)))
            val_losses.append(float(m.group(2)))
            r2s.append(float(m.group(3)))
    
    if not epochs:
        continue
    
    ax1.plot(epochs, r2s, marker='o', markersize=3, label=label, linewidth=1.5)
    ax2.plot(epochs, val_losses, marker='o', markersize=3, label=label, linewidth=1.5)

ax1.set_xlabel('Epoch', fontsize=12)
ax1.set_ylabel('R² median (val)', fontsize=12)
ax1.set_title('Per-case R² (inline, for trend only)', fontsize=13)
ax1.legend(fontsize=9)
ax1.grid(True, alpha=0.3)
ax1.set_xlim(0, 1050)

ax2.set_xlabel('Epoch', fontsize=12)
ax2.set_ylabel('Val Loss (masked L1)', fontsize=12)
ax2.set_title('Validation Loss', fontsize=13)
ax2.legend(fontsize=9)
ax2.grid(True, alpha=0.3)
ax2.set_xlim(0, 1050)

plt.tight_layout()
out_path = f"{BASE}/campaigns/grid18_top3_1k/r2_epoch_curves.png"
plt.savefig(out_path, dpi=150, bbox_inches='tight')
print(f"Saved to {out_path}")

# Also save locally accessible copy
plt.savefig("/tmp/r2_epoch_curves.png", dpi=150, bbox_inches='tight')
print("Also saved to /tmp/r2_epoch_curves.png")
