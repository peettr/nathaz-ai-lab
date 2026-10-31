"""Complete only missing official HRRR analysis/stat fields after archive collision.

Never overwrite a pre-existing file. Require byte-for-byte equality on collisions.
"""
import hashlib
import os
import zipfile
from fetch_archives import BASE, HTTPRange, ROOT

z = zipfile.ZipFile(HTTPRange(BASE+'data.zip'))
dest = os.path.join(ROOT, 'repo', 'AERO_ODE')
for member in z.infolist():
    name = member.filename
    if member.is_dir(): continue
    wanted = name.startswith('data/hrrr_stat/') or (name.startswith('data/hrrr_test/04/') and name.rsplit('/',1)[-1][:2] in {f'{i:02d}' for i in range(1,11)})
    if not wanted: continue
    if os.path.isabs(name) or '..' in name.split('/'):
        raise ValueError(name)
    target = os.path.join(dest, name)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if os.path.exists(target):
        with z.open(member) as f:
            original = hashlib.sha256(f.read()).digest()
        with open(target,'rb') as f:
            installed = hashlib.sha256(f.read()).digest()
        if original != installed: raise RuntimeError(f'existing repo file differs from HF: {name}')
        print('verified-existing', name, flush=True)
        continue
    print('extract', name, member.file_size, flush=True)
    with z.open(member) as src, open(target,'xb') as out:
        while data := src.read(1024*1024): out.write(data)
