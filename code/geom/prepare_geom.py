#!/usr/bin/env python3
"""Package original, hash-verified input for geometry-only CRC job."""
from pathlib import Path
import shutil, hashlib, gzip, json
base=Path('./26_Quick_Trials/06_Logs/L26.21/G1/meshconv')
out=base/'geom'
for grade in ('medium','fine'):
    src=base/'v2'/grade
    dst=out/'package'/grade
    if dst.exists(): raise SystemExit(f'Already exists: {dst}')
    dst.mkdir(parents=True)
    shutil.copytree(src/'case_inputs',dst/'case_inputs')
    for file in ('snappyHexMeshDict_B2','fvSolution_C1','inputs.sha256'):
        shutil.copy2(src/file,dst/file)
    ref=next((base/'returned_v2'/grade).glob('*meshconv_directions.json.gz'))
    shutil.copy2(ref,dst/'reference_directions.json.gz')
    hashes={}
    for line in (src/'inputs.sha256').read_text().splitlines():
        digest,name=line.split(maxsplit=1)
        if name.startswith('case_inputs/') or name in ('snappyHexMeshDict_B2','fvSolution_C1'):
            assert hashlib.sha256((dst/name).read_bytes()).hexdigest()==digest,name
            hashes[name]=digest
    (dst/'frozen_inputs.json').write_text(json.dumps(hashes,indent=2)+'\n')
print('PACKAGED', ', '.join(str(out/'package'/g) for g in ('medium','fine')))
