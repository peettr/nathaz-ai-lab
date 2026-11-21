#!/usr/bin/env python3
"""Freeze retry scripts from v2 without touching prior roots."""
from pathlib import Path
import difflib
p=Path(__file__).resolve().parent
for grade in ('coarse','medium'):
    source=p/'solve_v2'/f'g1_{grade}.qsub'
    target=p/'solve_v3'/f'g1_{grade}_v3.qsub'
    text=source.read_text()
    text=text.replace(f'L26_21_G1_{grade}',f'L26_21_G1_{grade}_v3')
    text=text.replace(f'L26_21_DAFOAM_20261114_G1_{grade}',f'L26_21_DAFOAM_20261114_G1_{grade}_v3')
    start=text.index('stage empty START\n')
    end=text.index('stage "$G/mesh" START\n')
    text=text[:start]+'''stage empty REUSED_FROM_FIRST_G1
[ -s "$C/empty_reference.json" ] || exit 26
stage empty END
cap || exit 92
'''+text[end:]
    marker='stage "$G/solve" START\n'
    check='''stage "$G/boundaries" START
python "$R/check_field_boundaries.py" "$C" > "$R/logs/boundary_check.log" 2>&1; rc=$?
stage "$G/boundaries" "rc=$rc"; [ "$rc" -eq 0 ] || exit 28
'''
    assert text.count(marker)==1
    text=text.replace(marker,check+marker)
    # Old script pre-checks an empty-case blockMeshDict even though reused empty case does not run.
    text=text.replace('"$E/system/blockMeshDict"','"$C/empty_reference.json" "$C/constant/polyMesh/boundary"')
    target.write_text(text)
    (p/'solve_v3'/f'v2_to_{grade}_v3.diff').write_text(''.join(difflib.unified_diff(source.read_text().splitlines(True),text.splitlines(True),fromfile=str(source),tofile=str(target))))
    print(target)
