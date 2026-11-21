from pathlib import Path
import hashlib, zipfile
parts=sorted(Path('/content').glob('v5part_*'))
assert len(parts)==9, [str(p) for p in parts]
out=Path('/content/urbantales_native_v5.zip')
with out.open('xb') as f:
    for part in parts:
        with part.open('rb') as g:
            while block:=g.read(4*1024*1024): f.write(block)
sha=hashlib.file_digest(out.open('rb'),'sha256').hexdigest()
assert sha=='f34e7da534e419f29fbcea1422848304a83af55d7df5ce225bc3eeb980c4fba9',sha
with zipfile.ZipFile(out) as z:
    assert len(z.namelist())==505 and z.testzip() is None
print('ASSEMBLED',out.stat().st_size,sha,flush=True)
