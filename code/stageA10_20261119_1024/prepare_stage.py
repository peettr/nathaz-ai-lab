#!/usr/bin/env python3
"""Stage sealed seven-source A9 archive, without changing the upstream result."""
from pathlib import Path
import hashlib, json, shutil, tarfile
R=Path(__file__).resolve().parent
A9=R.parent/'stageA9_20261119_101411'
base=A9/'stage/FluidX3D_on'
variants=('periodic_bounce','periodic_t4','periodic_t15_k2','periodic_t15_k3','legacy_off','legacy_on','legacy_k3')
out=R/'pack_stage'
if out.exists(): raise SystemExit('pack_stage exists: no overwrite')
out.mkdir()
hash_file=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'variants':{},'source_A9_result_sha256':hash_file(A9/'PREFLIGHT_RESULT_A9.json')}
for name in variants:
 d=out/name
 shutil.copytree(base,d)
 shutil.copytree(A9/'seven_variants_A9'/name,d/'src',dirs_exist_ok=True,ignore=shutil.ignore_patterns('emit','*.log','generated.cl','*.o','*.a','*.so'))
 for p in (d/'src').rglob('*.log'):p.unlink()
 e=d/'src/defines.hpp'
 manifest['variants'][name]={n:hash_file(d/'src'/n) for n in ('defines.hpp','kernel.cpp','lbm.cpp','setup.cpp')}
# Archive paths under pack_stage; worker checks members before extracting.
archive=R/'t17_stage.tar.gz'
if archive.exists(): raise SystemExit('archive exists: no overwrite')
with tarfile.open(archive,'w:gz') as t:t.add(out,arcname='pack_stage')
manifest['archive_sha256']=hash_file(archive)
(R/'t17_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'archive_sha256':manifest['archive_sha256'],'variants':list(manifest['variants'])}))
