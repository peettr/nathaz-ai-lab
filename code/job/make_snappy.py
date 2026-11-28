#!/usr/bin/env python3
"""L22.11 3b：由细档 snappyHexMeshDict_B2 生成带盒式加密区 box3b 的版本（实验卡 ② 写定）。用法：make_snappy.py <源> <目标> <A|B|C>"""
import sys, re
src, dst, cand = sys.argv[1:4]
box = {'A': ((-16, -16, 0), (16, 16, 16)), 'B': ((-12, -12, 0), (12, 12, 12)), 'C': ((-24, -20, 0), (24, 20, 20))}[cand]
s = open(src).read()
assert 'refinementRegions { }' in s and 'maxLocalCells 1200000;' in s and 'maxGlobalCells 1600000;' in s
s = s.replace('bottom.stl {type triSurfaceMesh; name bottom;} }',
              'bottom.stl {type triSurfaceMesh; name bottom;}\nbox3b {type searchableBox; min (%g %g %g); max (%g %g %g);} }' % (*box[0], *box[1]), 1)
assert 'box3b {type searchableBox' in s
s = s.replace('refinementRegions { }', 'refinementRegions { box3b { mode inside; levels ((1E15 1)); } }', 1)
s = s.replace('maxLocalCells 1200000;', 'maxLocalCells 3000000;').replace('maxGlobalCells 1600000;', 'maxGlobalCells 4000000;')
open(dst, 'w').write(s); print('SNAPPY_3B', cand, box)
