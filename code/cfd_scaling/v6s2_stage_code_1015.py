from pathlib import Path
import hashlib,tarfile
root=Path('/content/v6_work')
assert not root.exists()
root.mkdir()
p=Path('/content/v6s2_code.tar.gz')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='13d73c17dc78f0f9ed3025f848baee8385c4ba25f7eb75afc9f6c0da347b168d'
with tarfile.open(p) as t:t.extractall(root,filter='data')
print('CODE_OK',p.stat().st_size,flush=True)
