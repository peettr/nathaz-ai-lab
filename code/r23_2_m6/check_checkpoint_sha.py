import hashlib, pathlib
p=pathlib.Path('/content/m6/test_checkpoint.tgz')
print('checkpoint',p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest())
q=pathlib.Path('/content/m6/test_progress.jsonl')
print('progress last',q.read_text().splitlines()[-1])
