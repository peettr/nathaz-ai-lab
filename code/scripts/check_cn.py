import torch
d = torch.load("/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset/data/full_masked_640/train.pt", map_location="cpu", weights_only=False)
cn = d["case_names"]
x_shape = d["X"].shape[0]
print(f"train case_names length: {len(cn)}")
print(f"train X shape: {x_shape}")
print(f"Unique names: {len(set(cn))}")
if len(cn) != x_shape:
    print("MISMATCH: case_names length != X shape")

d2 = torch.load("/groups/kareem/[用户]/graph-deeponet-wind/auto_v2/full_dataset/data/full_masked_640/test.pt", map_location="cpu", weights_only=False)
cn2 = d2["case_names"]
x2_shape = d2["X"].shape[0]
print(f"test case_names length: {len(cn2)}")
print(f"test X shape: {x2_shape}")
print(f"Unique names: {len(set(cn2))}")
