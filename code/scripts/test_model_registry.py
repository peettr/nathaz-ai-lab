import sys, os, torch
sys.path.insert(0, "/groups/kareem/[用户]/graph-deeponet-wind/auto_v3")

# Test 1: Direct import
from shared.models.unet_v2_baseline import UNetV2Baseline
m = UNetV2Baseline(n_c=16)
p = sum(x.numel() for x in m.parameters())
print(f"Direct: UNetV2Baseline(n_c=16) = {p:,}")

m2 = UNetV2Baseline(n_c=32)
p2 = sum(x.numel() for x in m2.parameters())
print(f"Direct: UNetV2Baseline(n_c=32) = {p2:,}")

# Test 2: Via registry
from shared.models import REGISTRY
print(f"Registry entries: {REGISTRY.list_all()}")
cls = REGISTRY.get("unet_v2_baseline")
print(f"Registry class: {cls}")
m3 = cls(n_c=16)
p3 = sum(x.numel() for x in m3.parameters())
print(f"Registry: UNetV2Baseline(n_c=16) = {p3:,}")

m4 = cls(**{"n_c": 32, "training": {"scheduler": "cosine"}})
p4 = sum(x.numel() for x in m4.parameters())
print(f"Registry with training kwarg: n_c=32 = {p4:,}")

# Test 3: Simulate what train.py does
from shared.configs.schema import TrainConfig
import json
with open("/groups/kareem/[用户]/graph-deeponet-wind/auto_v3/campaigns/grid18/run_15/train_config.json") as f:
    cfg_dict = json.load(f)
print(f"\nConfig arch_name: {cfg_dict['arch_name']}")
print(f"Config arch_kwargs: {cfg_dict['arch_kwargs']}")
cls2 = REGISTRY.get(cfg_dict["arch_name"])
m5 = cls2(**cfg_dict["arch_kwargs"])
p5 = sum(x.numel() for x in m5.parameters())
print(f"From config: params = {p5:,}")

# Check what run_15 actually loaded
print(f"\nExpected: ~34.6M for n_c=16, ~251M for n_c=32")
print(f"Actually seen: 138M = UNet(depth=7, n_c=16) which is v3 model")
