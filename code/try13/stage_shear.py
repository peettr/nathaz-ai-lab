#!/usr/bin/env python3
"""Prepare isolated shear fixture; no host-side computation."""
from pathlib import Path
import shutil, hashlib, tarfile, json, difflib
R=Path(__file__).resolve().parent
src=R/'FluidX3D_noshear'
dst=R/'shear_stage/FluidX3D_gate0'
assert src.is_dir() and not dst.exists()
shutil.copytree(src,dst)
k=dst/'src/kernel.cpp'; before=k.read_text()
needle='if(usq>1.0e-16f && false) {'
assert before.count(needle)==1
k.write_text(before.replace(needle,'if(usq>1.0e-16f) {'))
sp=dst/'src/setup.cpp'; old=sp.read_text()
assert 'try13_noshear_wall.csv' in old
sp.write_text(old.replace('try13_noshear_wall.csv','try13_shear_wall.csv'))
out=R/'shear_stage'
(out/'shear.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),k.read_text().splitlines(True),fromfile='noshear/kernel.cpp',tofile='shear/kernel.cpp')))
names=('setup.cpp','kernel.cpp','lbm.cpp','lbm.hpp','defines.hpp')
hashes={name:hashlib.sha256((dst/'src'/name).read_bytes()).hexdigest() for name in names}
archive=out/'try13_shear.tar.gz'
with tarfile.open(archive,'w:gz') as tf:tf.add(dst,arcname='FluidX3D_gate0')
(out/'shear_manifest.json').write_text(json.dumps({'sources':hashes,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},indent=2)+'\n')
print(json.dumps(hashes,indent=2))
