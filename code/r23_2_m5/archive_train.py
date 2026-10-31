from pathlib import Path
import tarfile,hashlib
p=Path('/content/m5'); out=p/'train_checkpoint_20261027.tgz'
with tarfile.open(out,'w:gz') as t:
    for name in ['train_gfs','obs','progress.jsonl','errors.jsonl','train_gfs.log','stations.json']:
        if (p/name).exists():t.add(p/name,arcname=name)
print(out, out.stat().st_size, hashlib.sha256(out.read_bytes()).hexdigest())
