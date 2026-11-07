import numpy as np, sys, os, re, xarray
sys.path.insert(0, "/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset/references")
from data_formatter_fixed import DataFormatterFixed as DataFormatter

cn = "AR-BA-V1_d00"
case_dir = "/groups/kareem/[用户]/graph-deeponet-wind/data/urbantales/raw/" + cn
topo = np.flipud(np.loadtxt(os.path.join(case_dir, cn+"_topo"), dtype=np.float32))
with xarray.open_dataset(os.path.join(case_dir, cn+"_ped.nc")) as ds:
    Uped = ds["Uped"].values.astype(np.float32)
combined = Uped.copy()
combined[topo > 0] = -topo[topo > 0]
m = re.search(r"_d(\d+)$", cn)
angle = int(m.group(1))

print(f"combined shape: {combined.shape}")
formatter = DataFormatter(raw_data=[combined], wind_angles=[angle], formatted_shape=640)
print(f"_fmt_input_data shape: {np.shape(formatter._fmt_input_data)}")
fmt = formatter.format_input_data()
print(f"formatted shape: {np.shape(fmt)}")
restored = formatter.restore_raw_output_data(fmt)
print(f"restored shape: {np.shape(restored)}")
