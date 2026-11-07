"""GPU-only AERO-ODE correction-network 48-frame fwd+bwd timing.

Synthetic tensors match published tensor geometry; excludes frozen NeuralGCM,
I/O and HRRR preprocessing. Real weights are loaded only with weights_only=True.
"""
import json
import os
import sys
import time
from pathlib import Path

import torch

ROOT = Path('/groups/kareem/[用户]/L26_4_AERO_ODE_20261019/repo/AERO_ODE')

def measure(name, model_dir, model_class, kwargs, channels, static_channels, weight):
    sys.path.insert(0, str(ROOT/model_dir))
    import inference_components
    cls = getattr(inference_components, model_class)
    torch.cuda.empty_cache()
    model = cls(**kwargs).cuda().train()
    checkpoint = torch.load(str(ROOT/weight), map_location='cpu', weights_only=True)
    state = {k.removeprefix('module.'): v for k, v in checkpoint['model_state_dict'].items()}
    model.load_state_dict(state)
    del checkpoint
    x = torch.randn(1, channels, 440, 408, device='cuda')
    static = torch.randn(1, static_channels, 440, 408, device='cuda')
    time_index = torch.zeros(1, dtype=torch.long, device='cuda')
    opt = torch.optim.AdamW(model.parameters(), lr=1e-4)
    # Full 48-frame training sample; release each frame graph after backward.
    frames = int(os.environ.get('BENCH_FRAMES', '48'))
    torch.cuda.synchronize()
    start = time.perf_counter()
    opt.zero_grad(set_to_none=True)
    for frame in range(frames):
        output = model(x, static, time_index + frame, time_index + frame % 24, time_index + 4)
        (output.square().mean() / frames).backward()
    opt.step()
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    result = {'network': name, 'frames': frames, 'seconds_fwd_bwd_optimizer': elapsed,
              'gpu': torch.cuda.get_device_name(0), 'peak_gpu_bytes': torch.cuda.max_memory_allocated(),
              'batch_size': 1, 'tensor_shape': [1, channels, 440, 408],
              'static_shape': [1, static_channels, 440, 408],
              'definition': '48 synthetic hourly frames, real model weights, forward+backward per frame plus one AdamW step; frozen NeuralGCM excluded'}
    del model, x, static, output, opt
    sys.modules.pop('inference_components', None)
    print(json.dumps(result), flush=True)
    return result

if __name__ == '__main__':
    assert torch.cuda.is_available(), 'GPU required'
    results = []
    results.append(measure('AIR', 'AERO_AIR_WD', 'CorrectionModel',
                           {'time_emb_dim':128, 'backbone':'unet3plus'}, 70, 5,
                           'AERO_AIR_WD/checkpoints_film_25/model_ep5.pth'))
    results.append(measure('Surface', 'AERO_Surface_WD', 'DiagnosisModel',
                           {'in_channels_dynamic':74, 'in_channels_static':14,
                            'out_channels':4, 'time_emb_dim':128, 'backbone':'unet3plus'}, 74, 14,
                           'AERO_Surface_WD/checkpoints_film_v2/model_ep5.pth'))
    with open(os.environ['BENCH_OUTPUT'], 'x') as f:
        json.dump(results, f, indent=2)
