import numpy as np, sys, os, re, xarray
sys.path.insert(0, "/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset/references")
from data_formatter_fixed import DataFormatterFixed as DataFormatter

# Check how patches are ordered for a multi-patch case
import torch
train_pt = torch.load("/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset/data/full_masked_640/train.pt", map_location="cpu", weights_only=False)
test_pt = torch.load("/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset/data/full_masked_640/test.pt", map_location="cpu", weights_only=False)

train_cn = train_pt["case_names"]
test_cn = test_pt["case_names"]
train_p2c = train_pt["patch_to_case"]
test_p2c = test_pt["patch_to_case"]

# Find a multi-patch case in train
from collections import Counter
all_p2c = []
for i in range(len(train_p2c)):
    all_p2c.append((train_cn[int(train_p2c[i])], "train", i))
for i in range(len(test_p2c)):
    all_p2c.append((test_cn[int(test_p2c[i])], "test", i))

cn_counts = Counter(x[0] for x in all_p2c)
multi = {k: v for k, v in cn_counts.items() if v > 1}
print(f"Multi-patch cases: {len(multi)}")

# Show AR-BA-V1_d00 patches
cn = "AR-BA-V1_d00"
patches = [(x[1], x[2]) for x in all_p2c if x[0] == cn]
print(f"\n{cn}: {len(patches)} patches")
for src, idx in patches:
    print(f"  {src}[{idx}]")

# Create formatter for this case and check expected patches
case_dir = "/groups/kareem/[用户]/graph-deeponet-wind/data/urbantales/raw/" + cn
topo = np.flipud(np.loadtxt(os.path.join(case_dir, cn+"_topo"), dtype=np.float32))
with xarray.open_dataset(os.path.join(case_dir, cn+"_ped.nc")) as ds:
    Uped = ds["Uped"].values.astype(np.float32)
combined = Uped.copy()
combined[topo > 0] = -topo[topo > 0]
m = re.search(r"_d(\d+)$", cn)
angle = int(m.group(1))

formatter = DataFormatter(raw_data=[combined], wind_angles=[angle], formatted_shape=640)
print(f"\nFormatter _fmt_input_data shape: {np.shape(formatter._fmt_input_data)}")
print(f"Expected patches from formatter: {np.shape(formatter._fmt_input_data)[0]}")
