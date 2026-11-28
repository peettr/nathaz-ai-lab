#!/usr/bin/env python3
"""A700（委托 #8e913b84）：把已生成的 snappyHexMeshDict 中五面的 nSurfaceLayers 5 改为本档层数。用法：set_layers.py <snappyHexMeshDict> <n>"""
import sys
p, n = sys.argv[1], int(sys.argv[2]); s = open(p).read()
a = 'layers { "(xneg|xpos|yneg|ypos|roof)" { nSurfaceLayers 5; } }'
assert s.count(a) == 1
open(p, 'w').write(s.replace(a, 'layers { "(xneg|xpos|yneg|ypos|roof)" { nSurfaceLayers %d; } }' % n)); print('LAYERS', n)
