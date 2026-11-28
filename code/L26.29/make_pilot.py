#!/usr/bin/env python3
"""Generate immutable L26.29 formal-grid timing pilot (no solver execution)."""
import argparse
import hashlib
import json
import math
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('root', type=Path)
p.add_argument('--angular', type=int, default=240)
p.add_argument('--radial', type=int, default=590)
p.add_argument('--steps', type=int, default=60)
a = p.parse_args()
r = a.root
assert not r.exists(), f'Existing root is immutable: {r}'
assert a.angular % 4 == 0
for sub in ('0', 'constant', 'system'):
    (r / sub).mkdir(parents=True, exist_ok=False)

def put(name, text):
    (r/name).write_text(text)

def header(cls, obj):
    return f'FoamFile\n{{\n version 2.0; format ascii; class {cls}; object {obj};\n}}\n'

ang = [(-math.pi/4+i*math.pi/2) for i in range(4)]
pts=[]
for z in (-0.05,0.05):
    for radius in (0.5,):
        for t in ang:
            pts.append((radius*math.cos(t),radius*math.sin(t),z))
    for x,y in [(25,-25),(25,25),(-25,25),(-25,-25)]:
        pts.append((x,y,z))
assert len(pts)==16
verts='\n'.join('    (%.12g %.12g %.12g)' % xyz for xyz in pts)
blocks=[]
for i in range(4):
    j=(i+1)%4
    blocks.append(f'    hex ({i} {i+4} {j+4} {j} {i+8} {i+12} {j+12} {j+8}) ({a.radial} {a.angular//4} 1) simpleGrading (30 1 1)')
edges=[]
for k in (0,8):
    for i in range(4):
        j=(i+1)%4
        t=ang[i]+math.pi/4
        edges.append('    arc %d %d (%.12g %.12g %.12g)' %(i+k,j+k,.5*math.cos(t),.5*math.sin(t),-.05 if k==0 else .05))
def outer(i):
    j=(i+1)%4
    return f'({i+4} {i+12} {j+12} {j+4})'
def inner(i):
    j=(i+1)%4
    return f'({i} {j} {j+8} {i+8})'
def fb(i, top):
    j=(i+1)%4; off=8 if top else 0
    return f'({i+off} {i+4+off} {j+4+off} {j+off})'
patches=f'''    inlet {{ type patch; faces ({outer(2)} {outer(1)} {outer(3)}); }}
    outlet {{ type patch; faces ({outer(0)}); }}
    cylinder {{ type wall; faces ({' '.join(inner(i) for i in range(4))}); }}
    frontAndBack {{ type empty; faces ({' '.join(fb(i,t) for t in (False,True) for i in range(4))}); }}'''
put('system/blockMeshDict',header('dictionary','blockMeshDict')+'convertToMeters 1;\nvertices\n(\n'+verts+'\n);\nblocks\n(\n'+'\n'.join(blocks)+'\n);\nedges\n(\n'+'\n'.join(edges)+'\n);\nboundary\n(\n'+patches+'\n);\nmergePatchPairs ();\n')
put('0/U',header('volVectorField','U')+'''dimensions [0 1 -1 0 0 0 0];
internalField uniform (1 0 0);
boundaryField {
 inlet { type fixedValue; value uniform (1 0 0); }
 outlet { type zeroGradient; }
 cylinder { type noSlip; }
 frontAndBack { type empty; }
}
''')
put('0/p',header('volScalarField','p')+'''dimensions [0 2 -2 0 0 0 0];
internalField uniform 0;
boundaryField {
 inlet { type zeroGradient; }
 outlet { type fixedValue; value uniform 0; }
 cylinder { type zeroGradient; }
 frontAndBack { type empty; }
}
''')
put('constant/physicalProperties',header('dictionary','physicalProperties')+'viscosityModel constant; nu 0.01;\n')
put('constant/momentumTransport',header('dictionary','momentumTransport')+'simulationType laminar;\n')
put('system/fvSchemes',header('dictionary','fvSchemes')+'''ddtSchemes { default backward; }
gradSchemes { default Gauss linear; }
divSchemes { default none; div(phi,U) Gauss linearUpwind grad(U); }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
''')
put('system/fvSolution',header('dictionary','fvSolution')+'''solvers {
 p { solver GAMG; tolerance 1e-8; relTol 0.01; smoother GaussSeidel; }
 pFinal { $p; relTol 0; }
 U { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-9; relTol 0.01; }
 UFinal { $U; relTol 0; }
}
PIMPLE { momentumPredictor yes; nOuterCorrectors 1; nCorrectors 2; nNonOrthogonalCorrectors 0; }
''')
put('system/decomposeParDict',header('dictionary','decomposeParDict')+'numberOfSubdomains 4; method scotch;\n')
put('system/controlDict',header('dictionary','controlDict')+f'''application pimpleFoam;
startFrom startTime;
startTime 0;
stopAt endTime;
endTime {a.steps*.005:.6f};
deltaT 0.005;
writeControl timeStep;
writeInterval 60;
purgeWrite 0;
writeFormat binary;
writePrecision 8;
timeFormat general;
runTimeModifiable false;
functions {{
 forces {{
 type forces; libs ("libforces.so"); patches (cylinder);
 rho rhoInf; rhoInf 1; CofR (0 0 0);
 writeControl timeStep; writeInterval 1;
 }}
}}
''')
put('run.sh',f'''#!/bin/bash
#$ -cwd
#$ -pe smp 4
#$ -l h_rt=02:00:00
#$ -l mem_free=2G
#$ -N L26_29_pilot
ROOT="$(pwd)"
trap 'printf "%s\\n" "$?" > "$ROOT/run.exitcode"' EXIT
module load openfoam/10.0/gcc/11.5.0
set -euo pipefail
cd "$ROOT"
blockMesh > blockMesh.log 2>&1
checkMesh -allGeometry -allTopology > checkMesh.log 2>&1
if ! grep -q 'Mesh OK' checkMesh.log; then echo 'MESH_NOT_OK' >&2; exit 12; fi
decomposePar > decomposePar.log 2>&1
mpirun -np 4 pimpleFoam -parallel > pimpleFoam.log 2>&1
''')
(r/'run.sh').chmod(0o755)
manifest={str(x.relative_to(r)): hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(r.rglob('*')) if x.is_file()}
put('input_sha256.json',json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'root':str(r),'cells':a.angular*a.radial,'steps':a.steps,'inputs':manifest},indent=2))
