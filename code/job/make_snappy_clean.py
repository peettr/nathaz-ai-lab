#!/usr/bin/env python3
"""L22.11 clean（A686，卡 EXPERIMENT_CARD_clean.md ②）：由旧冻结 snappyHexMeshDict_B2（不改原文件）生成干净族配方，三档逐字相同：
去掉 bottom.stl（几何与表面加密两处）；近壁层同 v2（五面 5 层、第一层 0.04 m、ER 1.25、featureAngle 130）；单元上限放到 6e6/8e6（只是上限）。
用法：make_snappy_clean.py <源B2> <目标>"""
import sys
src, dst = sys.argv[1:3]
s = open(src).read()
def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)
rep('roof.stl {type triSurfaceMesh; name roof;}\nbottom.stl {type triSurfaceMesh; name bottom;} }', 'roof.stl {type triSurfaceMesh; name roof;} }')
rep('roof {level (2 2); patchInfo {type wall;} }\nbottom {level (2 2); patchInfo {type wall;} } } refinementRegions { }', 'roof {level (2 2); patchInfo {type wall;} } } refinementRegions { }')
rep('relativeSizes true; layers { roof { nSurfaceLayers 3; } } expansionRatio 1.2; finalLayerThickness 0.3; minThickness 0.1; nGrow 0; featureAngle 60;',
    'relativeSizes false; layers { "(xneg|xpos|yneg|ypos|roof)" { nSurfaceLayers 5; } } thicknessModel firstAndExpansion; firstLayerThickness 0.04; expansionRatio 1.25; minThickness 0.01; nGrow 0; featureAngle 130;')
rep('maxLocalCells 1200000;', 'maxLocalCells 6000000;'); rep('maxGlobalCells 1600000;', 'maxGlobalCells 8000000;')
assert 'bottom' not in s
open(dst, 'w').write(s); print('SNAPPY_CLEAN ok')
