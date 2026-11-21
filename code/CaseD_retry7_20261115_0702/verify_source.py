from pathlib import Path
import hashlib, json, tarfile
parts=sorted(Path('/content').glob('part_*'))
target=Path('/content/source_dd438c1.tar.gz')
assert len(parts)>1 and not target.exists()
h=hashlib.sha256()
with target.open('xb') as out:
    for part in parts:
        with part.open('rb') as src:
            for block in iter(lambda: src.read(1<<20), b''):
                out.write(block);h.update(block)
assert h.hexdigest()=='88ac44d3005dde28267a18f40fe6d5f5071105719ead40ca12509a5c492204d0'
with tarfile.open(target) as tar:
    hashes={}
    for entry in tar:
        if not entry.isfile():continue
        p=Path(entry.name)
        assert not p.is_absolute() and '..' not in p.parts
        v=hashlib.sha256()
        with tar.extractfile(entry) as stream:
            for block in iter(lambda:stream.read(1<<20),b''):v.update(block)
        hashes[str(p)]=v.hexdigest()
Path('/content/source_extracted_sha256.json').write_text(json.dumps(hashes,sort_keys=True))
print('SOURCE_VERIFIED',h.hexdigest(),'files',len(hashes),flush=True)
