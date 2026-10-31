import hashlib, pathlib
p=pathlib.Path('/content/m6/train_checkpoint.tgz')
print('remote_checkpoint', p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
