"""Disposable Colab compatibility repair for pinned Open3D CUDA wheel."""
import pathlib, subprocess, sys, traceback, json
p=pathlib.Path('/content/l26_19_wp')
try:
    subprocess.run([sys.executable,'-m','pip','install','--index-url','https://download.pytorch.org/whl/cu126','torch==2.13.0+cu126','torchvision==0.28.0+cu126'],check=True)
    import torch, open3d
    from open3d.ml.torch.python.layers.neighbor_search import RadiusSearch
    assert torch.__version__.startswith('2.13.') and torch.version.cuda=='12.6'
    print('REPAIR_OK',torch.__version__,torch.version.cuda,open3d.__version__,torch.cuda.get_device_name(),flush=True)
    (p/'repair_torch.json').write_text(json.dumps({'status':'ok','torch':torch.__version__,'cuda':torch.version.cuda,'open3d':open3d.__version__}))
except BaseException as e:
    traceback.print_exc()
    (p/'repair_torch.json').write_text(json.dumps({'status':'failed','error':repr(e),'trace':traceback.format_exc()}))
    raise
finally:
    (p/'repair_torch.done').write_text((p/'repair_torch.json').read_text()[:2000])
