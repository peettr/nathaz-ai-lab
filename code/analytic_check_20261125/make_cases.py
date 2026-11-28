#!/usr/bin/env python3
"""L26.11 analytic check: 5x5x5 hex boxes centred at the origin, cell sizes from reference.MESHES; one case per (lib, mesh)."""
import os, sys, json
here = os.path.dirname(os.path.abspath(__file__)); out = sys.argv[1]; NR = sys.argv[2]
ref = json.load(open(os.path.join(here, 'reference.json')))
LIBS = {'paper': 'libDEScoverPaper_f17f4d1', 'v3': 'libDEScoverDelta_v3'}
HDR = 'FoamFile\n{\n    version 2.0;\n    format ascii;\n    class %s;\n    object %s;\n}\n'
for lib, so in LIBS.items():
    for m, h in ref['meshes'].items():
        c = os.path.join(out, f'{lib}_{m}'); [os.makedirs(os.path.join(c, s), exist_ok=True) for s in ('0', 'constant', 'system')]
        lo = [-2.5*x for x in h]; hi = [2.5*x for x in h]
        open(f'{c}/system/blockMeshDict', 'w').write(HDR % ('dictionary', 'blockMeshDict') + f"""scale 1;
vertices ( ({lo[0]} {lo[1]} {lo[2]}) ({hi[0]} {lo[1]} {lo[2]}) ({hi[0]} {hi[1]} {lo[2]}) ({lo[0]} {hi[1]} {lo[2]})
           ({lo[0]} {lo[1]} {hi[2]}) ({hi[0]} {lo[1]} {hi[2]}) ({hi[0]} {hi[1]} {hi[2]}) ({lo[0]} {hi[1]} {hi[2]}) );
blocks ( hex (0 1 2 3 4 5 6 7) (5 5 5) simpleGrading (1 1 1) );
boundary ( walls {{ type patch; faces ( (0 4 7 3) (1 2 6 5) (0 1 5 4) (3 7 6 2) (0 3 2 1) (4 5 6 7) ); }} );
""")
        open(f'{c}/system/controlDict', 'w').write(HDR % ('dictionary', 'controlDict') + f"""application testLiutexDelta;
startFrom startTime; startTime 0; stopAt endTime; endTime 1; deltaT 1; writeControl timeStep; writeInterval 1;
libs ("{NR}/lib/{so}.so");
""")
        open(f'{c}/system/fvSchemes', 'w').write(HDR % ('dictionary', 'fvSchemes') + """ddtSchemes { default Euler; }
gradSchemes { default Gauss linear; }
divSchemes { default none; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
wallDist { method meshWave; }
""")
        open(f'{c}/system/fvSolution', 'w').write(HDR % ('dictionary', 'fvSolution') + 'solvers {}\n')
        open(f'{c}/constant/transportProperties', 'w').write(HDR % ('dictionary', 'transportProperties') + 'transportModel Newtonian;\nnu 1e-5;\n')
        open(f'{c}/constant/turbulenceProperties', 'w').write(HDR % ('dictionary', 'turbulenceProperties') + """simulationType LES;
LES
{
    LESModel        Smagorinsky;
    turbulence      on;
    printCoeffs     on;
    delta           DeltaLiutexTilde;
    DeltaLiutexTildeCoeffs { deltaCoeff 1.035; }
}
""")
        open(f'{c}/0/U', 'w').write(HDR % ('volVectorField', 'U') + 'dimensions [0 1 -1 0 0 0 0];\ninternalField uniform (0 0 0);\nboundaryField { walls { type fixedValue; value uniform (0 0 0); } }\n')
        open(f'{c}/0/nut', 'w').write(HDR % ('volScalarField', 'nut') + 'dimensions [0 2 -1 0 0 0 0];\ninternalField uniform 0;\nboundaryField { walls { type calculated; value uniform 0; } }\n')
# run script
lines = ['#!/bin/bash', 'set -u', f'NR={NR}', 'cd "$(dirname "$0")"']
for lib in LIBS:
    for m in ref['meshes']:
        lines.append(f'( cd {lib}_{m} && blockMesh > log.blockMesh 2>&1 ) || echo BLOCKMESH_FAIL {lib}_{m}')
        for k, v in ref['cases'].items():
            A = ' '.join(repr(x) for row in v['A'] for x in row)
            lines.append(f'( cd {lib}_{m} && $NR/bin/testLiutexDelta -A "({A})" > log.{k} 2>&1; echo "RC {lib} {m} {k} $?" ; grep RESULT log.{k} | sed "s/^/OUT {lib} {m} {k} /" )')
open(os.path.join(out, 'run_all.sh'), 'w').write('\n'.join(lines) + '\n')
print('ok')
