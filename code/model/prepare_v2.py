"""Disposable Colab preparation; no Drive, no credentials, no local bulk data."""
import hashlib, json, os, pathlib, subprocess, sys, time, traceback
from urllib.request import urlopen

ROOT = pathlib.Path('/content/l26_19_wp')
ROOT.mkdir(exist_ok=True)
LOG = ROOT / 'prepare_v2_state.json'

def run(*cmd):
    print('RUN', cmd, flush=True)
    subprocess.run(cmd, check=True)

def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

try:
    run(sys.executable, '-m', 'pip', 'install', '-q', 'open3d==0.20.0', 'pytorch-lightning==2.0.2', 'mdtraj==1.10.3', 'zstandard==0.25.0', 'msgpack==1.1.2', 'einops==0.8.2', 'pyyaml==6.0.3', 'huggingface_hub')
    repo = ROOT / 'repo'
    if not repo.exists():
        run('git', 'clone', '-q', 'https://github.com/WorldParticle/WorldParticle.git', str(repo))
    run('git', '-C', str(repo), 'checkout', '-q', 'b8e37b854f2af3fc9bfd7fc150cfc01cba4a092e')
    assert subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip() == 'b8e37b854f2af3fc9bfd7fc150cfc01cba4a092e'
    import torch, open3d, pytorch_lightning, yaml, huggingface_hub
    print('ENV', json.dumps(dict(python=sys.version, torch=torch.__version__, cuda=torch.version.cuda, open3d=open3d.__version__, lightning=pytorch_lightning.__version__, gpu=torch.cuda.get_device_name())), flush=True)
    weight = ROOT / 'final.ckpt'
    if not weight.exists():
        weight = pathlib.Path(huggingface_hub.hf_hub_download(repo_id='wclw1021/WorldParticle', repo_type='dataset', filename='fancy_fluid/checkpoint/final.ckpt', local_dir=str(ROOT / 'hf'), local_dir_use_symlinks=False))
    print('WEIGHT', str(weight), weight.stat().st_size, digest(weight), flush=True)
    assert weight.stat().st_size == 1880632297, 'unexpected checkpoint size'
    # No unsafe pickle fallback. An exception is terminal for this task.
    ckpt = torch.load(str(weight), map_location='cpu', weights_only=True)
    assert isinstance(ckpt, dict) and isinstance(ckpt.get('state_dict'), dict)
    print('WEIGHTS_ONLY_OK', len(ckpt['state_dict']), flush=True)
    state = dict(status='ok', weight=str(weight), sha256=digest(weight), size=weight.stat().st_size, torch=torch.__version__, cuda=torch.version.cuda, open3d=open3d.__version__, lightning=pytorch_lightning.__version__, python=sys.version.split()[0], gpu=torch.cuda.get_device_name(), keys=len(ckpt['state_dict']), repo='b8e37b854f2af3fc9bfd7fc150cfc01cba4a092e')
    LOG.write_text(json.dumps(state, indent=2))
except BaseException as exc:
    LOG.write_text(json.dumps(dict(status='failed', error=repr(exc), trace=traceback.format_exc()), indent=2))
    traceback.print_exc()
    raise
finally:
    (ROOT / 'prepare_v2.done').write_text(LOG.read_text()[:2000])
