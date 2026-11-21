#!/usr/bin/env python3
"""Prepare fresh, immutable-input G1 solve bundle from v5 accepted meshes.
This script operates only under this line's G1/solve_v2 local directory.
Remote mesh files are copied separately from the frozen CRC mesh root.
"""
import hashlib, json, re, shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
OUT=HERE/'solve_v2'
assert not OUT.exists(), f'preserve existing preparation: {OUT}'
ids={'coarse':[63353,82554,146897,161269,165033], 'medium':[110526,258499,460556,469790,471458]}
counts={'coarse':165806,'medium':500020}
for grade in ids:
    src=HERE/'review_v5/cases'/grade
    dst=OUT/'cases'/grade
    shutil.copytree(src,dst,ignore=shutil.ignore_patterns('polyMesh','processor*','0/C','__pycache__','*.pyc','*.log'))
    assert not (dst/'constant/polyMesh').exists()
    (dst/'sample_cells.json').write_text(json.dumps({'seed':2621,'cell_ids':ids[grade],'mesh_cells':counts[grade], 'source':'CRC G1_mesh_v5 0/C read-only preregistration'},indent=2)+'\n')
    cd=dst/'system/controlDict'
    s=cd.read_text();assert 'endTime 3000;' in s
    s=s.replace('endTime 3000;','endTime 5000;')
    # Per-iteration p roof mean and integrated force; yPlus final diagnostic.
    assert 'functions { roofMean' in s
    s=s.replace('functions { roofMean', 'functions { forcesX { type forces; libs ("libforces.so"); writeControl timeStep; writeInterval 1; patches (xneg xpos yneg ypos roof); rho rhoInf; rhoInf 1; CofR (0 0 0); } yPlusRoof { type yPlus; libs ("libfieldFunctionObjects.so"); writeControl timeStep; writeInterval 5000; } roofMean')
    cd.write_text(s)
    driver=dst/'g1_driver.py';shutil.copy2(HERE/'g1_driver_v2.py',driver)
    for f in ['0/U','0/k','0/omega','0/p','0/nut']:
        assert (dst/f).exists()
    assert 'maxBoundarySkewness 4' in (dst/'system/meshQualityDict').read_text()
    print(grade,counts[grade],hashlib.sha256((dst/'sample_cells.json').read_bytes()).hexdigest())
print('staged',OUT)
