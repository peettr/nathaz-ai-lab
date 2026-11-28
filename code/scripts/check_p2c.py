import torch
import numpy as np

d = torch.load("/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset/data/full_masked_640/train.pt", map_location="cpu", weights_only=False)
p2c = d["patch_to_case"]
cn = d["case_names"]
print(f"patch_to_case shape: {p2c.shape}")
print(f"patch_to_case range: {p2c.min().item()} - {p2c.max().item()}")
print(f"case_names count: {len(cn)}")

# Build per-patch case name
patch_cn = [cn[int(p2c[i])] for i in range(len(p2c))]
print(f"Per-patch names: {len(patch_cn)}")
print(f"Unique per-patch: {len(set(patch_cn))}")

# Show some multi-patch cases
from collections import Counter
cnt = Counter(patch_cn)
multi = {k: v for k, v in cnt.items() if v > 1}
print(f"Cases with >1 patch: {len(multi)}")
if multi:
    top = sorted(multi.items(), key=lambda x: -x[1])[:5]
    for k, v in top:
        print(f"  {k}: {v} patches")

# Same for test
d2 = torch.load("/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset/data/full_masked_640/test.pt", map_location="cpu", weights_only=False)
p2c2 = d2["patch_to_case"]
cn2 = d2["case_names"]
patch_cn2 = [cn2[int(p2c2[i])] for i in range(len(p2c2))]
cnt2 = Counter(patch_cn2)
multi2 = {k: v for k, v in cnt2.items() if v > 1}
print(f"Test: cases with >1 patch: {len(multi2)}")
