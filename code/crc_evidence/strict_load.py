import sys, types, logging, torch, yaml
R = "/groups/kareem/[用户]/L26.28_D0b_20261128/x/HybSR-TC/super_resolution/basicsr"
Y = "/groups/kareem/[用户]/L26.28_D0b_20261128/x/HybSR-TC/super_resolution/options/train/SwinIR/train_SwinIRGAN_multi_var_time_window_meta_upscale_typhoon_qc.yml"
W = "/groups/kareem/[用户]/L26.28_D0b_20261128/x/HybSR-TC/data/model/HybSR-TC_net_g_180000.pth"
def pkg(name, path=None):
    m = types.ModuleType(name); m.__path__ = [path] if path else []; sys.modules[name] = m; return m
pkg("basicsr", R); u = pkg("basicsr.utils"); u.get_root_logger = lambda *a, **k: logging.getLogger("x")
class Reg:
    def register(self, *a, **k): return a[0] if a and callable(a[0]) else (lambda f: f)
reg = types.ModuleType("basicsr.utils.registry"); reg.ARCH_REGISTRY = Reg(); sys.modules["basicsr.utils.registry"] = reg
pkg("basicsr.archs", R + "/archs"); pkg("basicsr.ops", R + "/ops"); pkg("basicsr.ops.meta_upscale", R + "/ops/meta_upscale")
torch.Tensor.cuda = lambda self, *a, **k: self
from basicsr.archs.swinir_multi_var_time_window_meta_arch import SwinIRMultiVarTimeWindowMetaUpsample as Net
cfg = yaml.safe_load(open(Y))
g = dict(cfg["network_g"]); g.pop("type")
ds = cfg["datasets"]["train"]
import inspect; sig = inspect.signature(Net.__init__).parameters
print("ctor params:", [p for p in sig][:40])
extra = {}
for k_cfg, k in [("lq_means","lq_means"),("lq_stds","lq_stds"),("gt_means","gt_means"),("gt_stds","gt_stds")]:
    if k in sig: extra[k] = ds[k_cfg]
net = Net(**g, **extra)
sd = torch.load(W, weights_only=True, map_location="cpu")
for key in ["params_ema", "params"]:
    r = net.load_state_dict(sd[key], strict=True); print(key, "strict OK", r)
print("n_params", sum(p.numel() for p in net.parameters()))
net.eval()
x = torch.randn(1, 29, 4, 21, 21)
with torch.no_grad():
    try:
        y = net(x); print("forward shape", tuple(y.shape) if hasattr(y,"shape") else type(y))
    except Exception as e: print("forward failed:", repr(e)[:300])
