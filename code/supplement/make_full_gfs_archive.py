import tarfile,hashlib
from pathlib import Path
p=Path('/content/m6');old=set();archive=sorted((p/'test_gfs').glob('*.csv'))
with tarfile.open(p/'test_checkpoint_1028_181649.tgz') as t:old={Path(m.name).name for m in t.getmembers() if m.isfile()}
fresh=[f for f in archive if f.name not in old]
assert len(archive)==368 and len(fresh)==18
dest=p/'test_gfs_full_20261029.tgz'
assert not dest.exists()
with tarfile.open(dest,'w:gz') as t:
    t.add(p/'test_gfs',arcname='test_gfs')
print('ARCHIVED',len(archive),'fresh',len(fresh),dest.stat().st_size,hashlib.sha256(dest.read_bytes()).hexdigest())
print('FRESH',','.join(sorted(f.name for f in fresh)))
