#!/usr/bin/env python3
"""Prepare an isolated v5 mesh input from v4; no solver execution."""
from pathlib import Path
import shutil
base = Path(__file__).resolve().parent
source = base / 'review_v4' / 'cases'
out = base / 'review_v5' / 'cases'
assert not out.exists(), out
for grade in ('coarse', 'medium'):
    src = source / grade
    dst = out / grade
    shutil.copytree(src, dst)
    q = dst / 'system' / 'meshQualityDict'
    old = q.read_text()
    assert old.count('maxBoundarySkewness 20;') == 1
    q.write_text(old.replace('maxBoundarySkewness 20;', 'maxBoundarySkewness 4;'))
    print(grade, dst, 'maxBoundarySkewness 4')
