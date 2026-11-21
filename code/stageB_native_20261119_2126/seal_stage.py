#!/usr/bin/env python3
"""Prepare immutable source archive/manifest. Never overwrites existing archive."""
import hashlib,json,pathlib,tarfile
R=pathlib.Path(__file__).resolve().parent
names={'bounce':'periodic_bounce','t4':'periodic_t4','t15':'periodic_t15_k2'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
archive=R/'t17b_stage.tar.gz'
if archive.exists():raise FileExistsError(archive)
variants={}
for group,name in names.items():
 src=R/'pack_stage'/name/'src'
 variants[name]={n:sha(src/n) for n in ('setup.cpp','kernel.cpp','lbm.cpp','defines.hpp','t17_b_native.inc')}
with tarfile.open(archive,'w:gz') as t:t.add(R/'pack_stage',arcname='pack_stage')
(R/'t17b_manifest.json').write_text(json.dumps({'archive_sha256':sha(archive),'variants':variants,'variant_names':names},indent=2)+'\n')
print('SEALED_STAGE',archive,sha(archive))
