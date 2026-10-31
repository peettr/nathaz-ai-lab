from pathlib import Path
import tarfile, hashlib
p=Path('/content/m4_v2_snapshot_20261024_2312.tgz')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='e86dfe22c7256860d857e756c3fece67e56f8f39ffa9cf0c98f1dc8f7fa370f5'
with tarfile.open(p) as tf:
    members=tf.getmembers()
    assert all((m.name=='m4' or m.name.startswith('m4/')) and not m.issym() and not m.islnk() for m in members)
    tf.extractall('/content',filter='data')
root=Path('/content/m4')
print('RESTORED',len(list(root.glob('gfs_train/*.csv'))),'GFS', (root/'train_pairs.parquet').stat().st_size,'TRAIN_PAIRS_BYTES')
assert len(list(root.glob('gfs_train/*.csv')))==1457
assert (root/'train_v2.exit').read_text().strip()=='0'
