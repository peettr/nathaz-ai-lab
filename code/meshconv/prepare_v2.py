"""Create fresh, disjoint meshconv v2 inputs; preserve originals."""
from pathlib import Path
import hashlib
import re
import shutil

base = Path(__file__).resolve().parent
out = base / 'v2'
assert not out.exists(), out
for grade in ('coarse', 'medium', 'fine'):
    src = base / grade
    dst = out / grade
    shutil.copytree(src, dst)
    (dst / 'inputs.sha256').unlink()
    qsub = dst / 'meshconv.qsub'
    text = qsub.read_text()
    oldroot = f'/groups/kareem/[用户]/L26_21_DAFOAM_20261120_meshconv/{grade}'
    newroot = f'/groups/kareem/[用户]/L26_21_DAFOAM_20261120_meshconv_v2/{grade}'
    assert text.count(oldroot) == 1
    text = text.replace(oldroot, newroot)
    text = text.replace(f'#$ -N L26_21_mc_{grade}', f'#$ -N L26_21_mc2_{grade}')
    text = text.replace(f'L26_21_mc_{grade}_XXXXXXXX', f'L26_21_mc2_{grade}_XXXXXXXX')
    qsub.write_text(text)
    worker = dst / 'meshconv_worker.sh'
    text = worker.read_text()
    old = '--env HOME="$W/home",TMPDIR="$W/tmp",NUMBA_CACHE_DIR="$W/numba"'
    new = old + ' --env MESHCONV_GRADE="$GRADE"'
    assert text.count(old) == 1
    worker.write_text(text.replace(old, new))
    if grade == 'fine':
        assert text.count('[ "$N" -le 760000 ]') == 1
        w = worker.read_text().replace('[ "$N" -le 760000 ]', '[ "$N" -le 800000 ]')
        worker.write_text(w)
    manifest = []
    for p in sorted(dst.rglob('*')):
        if p.is_file() and p.name != 'inputs.sha256':
            manifest.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(dst)}')
    (dst / 'inputs.sha256').write_text('\n'.join(manifest) + '\n')
    print(grade, newroot, hashlib.sha256(qsub.read_bytes()).hexdigest(), len(manifest))
