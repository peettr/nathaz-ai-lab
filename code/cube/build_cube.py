#!/usr/bin/env python3
"""Create a structured, conformal surface-mounted cube mesh and DAFoam SA case.
Only creates new files under supplied path; no solver execution on 工作站.
"""
from pathlib import Path
import sys, math, json
root=Path(sys.argv[1]); assert not root.exists(), root
for sub in ('system','constant','0'): (root/sub).mkdir(parents=True)
def h(cls,obj,loc): return f'FoamFile {{ version 2.0; format ascii; class {cls}; location "{loc}"; object {obj}; }}\n'
def put(rel,txt): (root/rel).write_text(txt)
# Paper fixes x_front=3.5H, y span=9H, H=1m; unspecified dimensions are assumptions.
xx=[0,3.5,4.5,13.5]; yy=[0,4,5,9]; zz=[0,1,4]
nx=[30,14,56]; ny=[25,14,25]; nz=[14,22]
vertices=[(x,y,z) for z in zz for y in yy for x in xx]
vid=lambda i,j,k:k*16+j*4+i
blocks=[]; patches={p:[] for p in ('inlet','outlet','sideNeg','sidePos','ground','top','front','back','cubeSideNeg','cubeSidePos','roof')}
faceidx={'xm':(0,4,7,3),'xp':(1,2,6,5),'ym':(0,1,5,4),'yp':(3,7,6,2),'zm':(0,3,2,1),'zp':(4,5,6,7)}
for k in range(2):
 for j in range(3):
  for i in range(3):
   if (i,j,k)==(1,1,0):continue
   v=[vid(i,j,k),vid(i+1,j,k),vid(i+1,j+1,k),vid(i,j+1,k),vid(i,j,k+1),vid(i+1,j,k+1),vid(i+1,j+1,k+1),vid(i,j+1,k+1)]
   # x/y uniform, lower z mild grading; above roof graded from roof upward.
   grading='(1 1 4)' if k==0 else '(1 1 8)'
   blocks.append(f'hex ({" ".join(map(str,v))}) ({nx[i]} {ny[j]} {nz[k]}) simpleGrading {grading}')
   for face, patch in [('xm','inlet' if i==0 else 'back' if (i,j,k)==(2,1,0) else None),('xp','outlet' if i==2 else 'front' if (i,j,k)==(0,1,0) else None),('ym','sideNeg' if j==0 else 'cubeSideNeg' if (i,j,k)==(1,2,0) else None),('yp','sidePos' if j==2 else 'cubeSidePos' if (i,j,k)==(1,0,0) else None),('zm','ground' if k==0 else 'roof' if (i,j,k)==(1,1,1) else None),('zp','top' if k==1 else None)]:
    if patch:patches[patch].append(tuple(v[t] for t in faceidx[face]))
# Check interior cube faces: front is x=3.5 face of upstream block; back x=4.5 downstream block.
assert len(blocks)==17 and all(patches.values())
blocktxt=h('dictionary','blockMeshDict','system')+'convertToMeters 1;\nvertices (\n'+''.join(f' ({x} {y} {z})\n' for x,y,z in vertices)+');\nblocks (\n'+'\n'.join(blocks)+'\n);\nedges ();\nboundary (\n'
for name,faces in patches.items():
 kind='wall' if name in ('ground','front','back','cubeSideNeg','cubeSidePos','roof') else 'patch'
 blocktxt+=f' {name} {{ type {kind}; faces ( '+ ' '.join('('+' '.join(map(str,f))+')' for f in faces)+' ); }\n'
blocktxt+=');\nmergePatchPairs ();\n'
put('system/blockMeshDict',blocktxt)
put('system/controlDict',h('dictionary','controlDict','system')+'application DASimpleFoam; startFrom startTime; startTime 0; stopAt endTime; endTime 3000; deltaT 1; writeControl timeStep; writeInterval 999999; purgeWrite 1; writeFormat ascii; writePrecision 12; runTimeModifiable false;\n')
put('system/fvSchemes',h('dictionary','fvSchemes','system')+'ddtSchemes {default steadyState;} gradSchemes {default Gauss linear;} divSchemes {default none; div(phi,U) bounded Gauss linearUpwind grad(U); div(phi,nuTilda) bounded Gauss upwind; div(pc) bounded Gauss upwind; div((nuEff*dev2(T(grad(U))))) Gauss linear;} laplacianSchemes {default Gauss linear corrected;} interpolationSchemes {default linear;} snGradSchemes {default corrected;} wallDist {method meshWave;}\n')
put('system/fvSolution',h('dictionary','fvSolution','system')+'solvers { p {solver GAMG; tolerance 1e-8; relTol 0.1; smoother GaussSeidel; maxIter 50;} "(U|nuTilda)" {solver smoothSolver; smoother GaussSeidel; tolerance 1e-9; relTol 0.1; maxIter 50;} } SIMPLE {nNonOrthogonalCorrectors 2; consistent no;} relaxationFactors {fields {p 0.2;} equations {"(U|nuTilda)" 0.5;}}\n')
put('system/decomposeParDict',h('dictionary','decomposeParDict','system')+'numberOfSubdomains 48; method scotch;\n')
put('constant/transportProperties',h('dictionary','transportProperties','constant')+'transportModel Newtonian; nu [0 2 -1 0 0 0 0] 2.5e-5; Pr 0.71; Prt 0.85;\n')
put('constant/turbulenceProperties',h('dictionary','turbulenceProperties','constant')+'simulationType RAS; RAS { RASModel SpalartAllmaras; turbulence on; printCoeffs on; }\n')
wall=['ground','front','back','cubeSideNeg','cubeSidePos','roof']
def field(obj,cls,dim,internal,values):
 text=h(cls,obj,'0')+f'dimensions {dim}; internalField uniform {internal}; boundaryField {{\n'
 for patch in patches:
  text+=f' {patch} {{ {values[patch]} }}\n'
 text+='}\n';put('0/'+obj,text)
def by(inc,out,w):return {p:(inc if p=='inlet' else out if p=='outlet' else w if p in wall else 'type slip;' if p in ('sideNeg','sidePos','top') else '') for p in patches}
U=by('type fixedValue; value uniform (1 0 0);','type zeroGradient;','type noSlip;')
for p in ('sideNeg','sidePos','top'):U[p]='type slip;'
field('U','volVectorField','[0 1 -1 0 0 0 0]','(1 0 0)',U)
p=by('type zeroGradient;','type fixedValue; value uniform 0;','type zeroGradient;')
for v in ('sideNeg','sidePos','top'):p[v]='type zeroGradient;'
field('p','volScalarField','[0 2 -2 0 0 0 0]','0',p)
nu=2.5e-5
sa=by(f'type fixedValue; value uniform {3*nu:.12g};','type zeroGradient;','type fixedValue; value uniform 0;')
for v in ('sideNeg','sidePos','top'):sa[v]='type zeroGradient;'
field('nuTilda','volScalarField','[0 2 -1 0 0 0 0]',f'{3*nu:.12g}',sa)
nut=by('type calculated; value uniform 0;','type calculated; value uniform 0;','type nutUSpaldingWallFunction; value uniform 0;')
for v in ('sideNeg','sidePos','top'):nut[v]='type calculated; value uniform 0;'
field('nut','volScalarField','[0 2 -1 0 0 0 0]','0',nut)
expected=sum(nx[i]*ny[j]*nz[k] for k in range(2) for j in range(3) for i in range(3) if (i,j,k)!=(1,1,0))
(root/'mesh_manifest.json').write_text(json.dumps({'expected_cells':expected,'blocks':len(blocks),'patch_faces':{p:len(v) for p,v in patches.items()},'domain_m':[xx,yy,zz],'subdivisions':[nx,ny,nz]},indent=2)+'\n')
print('generated',root,expected,'cells',len(blocks),'blocks', {p:len(v) for p,v in patches.items()})
