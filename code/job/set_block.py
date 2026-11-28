#!/usr/bin/env python3
"""把 blockMeshDict 的背景单元数 (150 80 58) 换成本档的 (Nx Ny Nz)（卡 ②，r=1.35）。用法：set_block.py <blockMeshDict> <coarse|medium|fine>"""
import sys
p, g = sys.argv[1:3]
n = {'coarse': (111, 59, 43), 'medium': (150, 80, 58), 'fine': (202, 108, 78)}[g]
s = open(p).read(); a = 'hex (0 1 2 3 4 5 6 7) (150 80 58) simpleGrading (1 1 8)'
assert s.count(a) == 1
open(p, 'w').write(s.replace(a, 'hex (0 1 2 3 4 5 6 7) (%d %d %d) simpleGrading (1 1 8)' % n)); print('BLOCK', g, n)
