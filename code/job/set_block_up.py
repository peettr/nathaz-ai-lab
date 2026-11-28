#!/usr/bin/env python3
"""L22.11 整族上移一档（委托 #00b9b555）：新粗 (150,80,58)=旧中、新中 (202,108,78)=旧细、新细 (273,146,105)。用法：set_block_up.py <blockMeshDict> <coarse|medium|fine>"""
import sys
p, g = sys.argv[1:3]
n = {'coarse': (150, 80, 58), 'medium': (202, 108, 78), 'fine': (273, 146, 105)}[g]
s = open(p).read(); a = 'hex (0 1 2 3 4 5 6 7) (150 80 58) simpleGrading (1 1 8)'
assert s.count(a) == 1
open(p, 'w').write(s.replace(a, 'hex (0 1 2 3 4 5 6 7) (%d %d %d) simpleGrading (1 1 8)' % n)); print('BLOCK_UP', g, n)
