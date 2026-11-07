from pathlib import Path
import hashlib
import json
import tarfile
import torch
root=Path('/content/v6_work')
root.mkdir(exist_ok=True)
with tarfile.open('/content/v6_code_bundle.tar.gz') as t:
    t.extractall(root,filter='data')
parts=sorted(Path('/content').glob('v6part[0-9][0-9][0-9]'))
print('gpu',torch.cuda.get_device_name(0),'vram_gb',torch.cuda.get_device_properties(0).total_memory/1e9,'torch',torch.__version__,'parts',len(parts),flush=True)
if len(parts)==65:
    p=root/'v6_legacy_code/all_data.pt'
    h=hashlib.sha256()
    with p.open('wb') as out:
        for part in parts:
            with part.open('rb') as f:
                while x:=f.read(2*1024*1024):
                    out.write(x)
                    h.update(x)
    print('DATA',p.stat().st_size,h.hexdigest(),flush=True)
    assert h.hexdigest()=='494c85166bfc958449dcf753467675cf8d6da429c7edad4a74ec740210c6a5b9'
