#!/usr/bin/env python3
"""L22.11 选 2（v2）：由旧冻结配置 snappyHexMeshDict_B2（不改原文件）生成墙面+屋面固定绝对厚度边界层的版本。
三档近壁层完全相同；finer 另加 3b 已选定的盒 C（同 3b make_snappy.py）。用法：make_snappy_v2.py <源B2> <目标> <medium|fine|finer>"""
import sys
src, dst, grade = sys.argv[1:4]
assert grade in ('medium', 'fine', 'finer')
s = open(src).read()
old = 'relativeSizes true; layers { roof { nSurfaceLayers 3; } } expansionRatio 1.2; finalLayerThickness 0.3; minThickness 0.1; nGrow 0; featureAngle 60;'
assert s.count(old) == 1, 'B2 addLayersControls 与预期不符'
new = ('relativeSizes false; layers { "(xneg|xpos|yneg|ypos|roof)" { nSurfaceLayers 5; } } '
       'thicknessModel firstAndExpansion; firstLayerThickness 0.04; expansionRatio 1.25; minThickness 0.01; nGrow 0; featureAngle 130;')
s = s.replace(old, new)
if grade == 'finer':
    assert 'refinementRegions { }' in s and 'maxLocalCells 1200000;' in s and 'maxGlobalCells 1600000;' in s
    s = s.replace('bottom.stl {type triSurfaceMesh; name bottom;} }',
                  'bottom.stl {type triSurfaceMesh; name bottom;}\nbox3b {type searchableBox; min (-24 -20 0); max (24 20 20);} }', 1)
    s = s.replace('refinementRegions { }', 'refinementRegions { box3b { mode inside; levels ((1E15 1)); } }', 1)
    s = s.replace('maxLocalCells 1200000;', 'maxLocalCells 3000000;').replace('maxGlobalCells 1600000;', 'maxGlobalCells 4000000;')
    assert 'box3b {type searchableBox' in s
open(dst, 'w').write(s); print('SNAPPY_V2', grade)
