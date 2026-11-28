#!/usr/bin/env python3
"""L22.11 clean 门 A 配方迭代（委托 #e72bef67：≤3 次，三档同一配方，门 A 阈值不改）。在 make_snappy_clean.py 的基础配方上叠加第 k 次改动。
用法：make_snappy_it.py <源B2> <源meshQualityDict> <目标snappy> <目标meshQualityDict> <k>"""
import sys, subprocess, os
b2, mq, dst, dmq, k = sys.argv[1:6]; k = int(k)
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'make_snappy_clean.py'), b2, dst], check=True)
s = open(dst).read(); q = open(mq).read()
def rep(t, a, b):
    assert t.count(a) == 1, a; return t.replace(a, b)
IT = {
 # 第 1 次：snappy 内部质量控制的非正交上限 65 → 58（门仍是 60）；加层与贴合迭代加多、内侧收缩判据放宽
 1: dict(mq=[('maxNonOrtho 65;', 'maxNonOrtho 58;')],
         s=[('nSolveIter 50; nRelaxIter 5; nFeatureSnapIter 10;', 'nSolveIter 100; nRelaxIter 8; nFeatureSnapIter 15;'),
            ('nRelaxIter 5; nSmoothSurfaceNormals 1;', 'nRelaxIter 10; nSmoothSurfaceNormals 1;'),
            ('maxThicknessToMedialRatio 0.3; minMedialAxisAngle 90;', 'maxThicknessToMedialRatio 0.6; minMedialAxisAngle 130;'),
            ('nLayerIter 10; nRelaxedIter 5;', 'nLayerIter 50; nRelaxedIter 20;')]),
}
IT[2] = dict(mq=IT[1]['mq'], s=IT[1]['s'] + [
    # 第 2 次：在第 1 次基础上加显式棱边贴合（surfaceFeatureExtract 取五个面 STL 的开放边，即建筑棱边与墙脚线），关隐式贴合
    ('features ();', 'features ( {file "xneg.eMesh"; level 2;} {file "xpos.eMesh"; level 2;} {file "yneg.eMesh"; level 2;} {file "ypos.eMesh"; level 2;} {file "roof.eMesh"; level 2;} );'),
    ('implicitFeatureSnap true; explicitFeatureSnap false;', 'implicitFeatureSnap false; explicitFeatureSnap true;')])
IT[3] = dict(mq=[('maxNonOrtho 65;', 'maxNonOrtho 60;')], s=[
    # 第 3 次（最后一次）：回到第 1 次的隐式贴合（第 2 次显式棱边贴合使细档屋面层数降到 3.84），自查非正交上限 58 → 60（=门），贴合容差与平滑加大，加层厚度比上限放宽
    ('nSmoothPatch 5; tolerance 1; nSolveIter 50; nRelaxIter 5; nFeatureSnapIter 10;', 'nSmoothPatch 10; tolerance 2; nSolveIter 100; nRelaxIter 8; nFeatureSnapIter 30;'),
    ('nRelaxIter 5; nSmoothSurfaceNormals 1;', 'nRelaxIter 10; nSmoothSurfaceNormals 1;'),
    ('nSmoothThickness 10; maxFaceThicknessRatio 0.5; maxThicknessToMedialRatio 0.3; minMedialAxisAngle 90;', 'nSmoothThickness 20; maxFaceThicknessRatio 0.8; maxThicknessToMedialRatio 0.6; minMedialAxisAngle 130;'),
    ('nLayerIter 10; nRelaxedIter 5;', 'nLayerIter 50; nRelaxedIter 20;')])
for a, b in IT[k]['s']: s = rep(s, a, b)
for a, b in IT[k]['mq']: q = rep(q, a, b)
open(dst, 'w').write(s); open(dmq, 'w').write(q)
if k >= 2:
    body = ''.join('%s.stl { extractionMethod extractFromSurface; extractFromSurfaceCoeffs { includedAngle 150; } subsetFeatures { nonManifoldEdges yes; openEdges yes; } writeObj no; }\n' % n for n in ('xneg', 'xpos', 'yneg', 'ypos', 'roof'))
    open(os.path.join(os.path.dirname(dst), 'surfaceFeatureExtractDict'), 'w').write('FoamFile { version 2.0; format ascii; class dictionary; object surfaceFeatureExtractDict; }\n' + body)
print('SNAPPY_IT', k)
