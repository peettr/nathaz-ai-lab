from pathlib import Path
import shutil, hashlib
base=Path('./26_Quick_Trials/06_Logs/L26.21')
out=base/'D0f'; src=base/'D0'/'cases'
assert not (out/'cases').exists(), 'new case copy already exists; preserve it'
shutil.copytree(src,out/'cases',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for grade in ('coarse','medium'):
    for p in sorted((out/'cases'/grade/'0').iterdir()):
        if not p.is_file(): continue
        s=p.read_text(); assert '"(sideNeg|sidePos|top)" {type symmetry;}' in s and 'bottom {' in s,(p,s)
        s=s.replace('"(sideNeg|sidePos|top)" {type symmetry;}','"(sideNeg|sidePos|top)" {type symmetryPlane;}').replace('bottom {','ground {')
        p.write_text(s)
        print(p.relative_to(out),hashlib.sha256(p.read_bytes()).hexdigest())
old=(base/'D0e'/'d0e_crc.qsub').read_text()
s=old.replace('D0e','D0f').replace('d0e','d0f')
s=s.replace('for grade in coarse medium; do\n', '''# Mesh is copied read-only from D0e to this fresh root; verify geometry again, do not regenerate.
for grade in coarse medium; do
''')
s=s.replace('  step "${grade}_blockMesh" "${grade}_block.log" /bin/bash -c "cd \'$C\' && blockMesh" || exit 20\n  step "${grade}_snappy" "${grade}_snappy.log" /bin/bash -c "cd \'$C\' && snappyHexMesh -overwrite" || exit 21\n','  [ -s "$C/constant/polyMesh/boundary" ] || exit 20\n')
assert 'step "${grade}_blockMesh"' not in s and 'snappyHexMesh -overwrite' not in s
(out/'d0f_crc.qsub').write_text(s)
print('qsub sha256',hashlib.sha256(s.encode()).hexdigest())
