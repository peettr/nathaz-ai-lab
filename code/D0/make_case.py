#!/usr/bin/env python3
"""Generate isolated TPU 0-degree D0 snappy/SST cases; no solver execution."""
from pathlib import Path
import argparse
import struct

p = argparse.ArgumentParser()
p.add_argument('root', type=Path)
p.add_argument('--level', type=int, choices=[1,2], required=True)
a=p.parse_args()
root=a.root
for d in ('0','constant/triSurface','system'):
    (root/d).mkdir(parents=True,exist_ok=True)
def put(name, body):
    (root/name).write_text(body)
def header(kind, obj, loc):
    return f'FoamFile {{ version 2.0; format ascii; class {kind}; location "{loc}"; object {obj}; }}\n'
# Full scale is used so TPU coordinates map directly and Re is explicit.
# ABL surrogate logarithmic profile U(z)=U*/kappa ln((z+z0)/z0), U(8)=10m/s.
# fixedValue via coded height faces is avoided; fixedValue nonuniform per-face list is
# produced on the compute node after snappy via a small OpenFOAM utility, if available.
# For this pilot use a spatially constant precursor profile at reference height;
# explicitly not a resolved ABL profile unless the profile conversion succeeds.
verts=[(-8,-8,0),(8,-8,0),(8,8,0),(-8,8,0),(-8,-8,8),(8,-8,8),(8,8,8),(-8,8,8)]
faces={'xneg':[(0,3,7),(0,7,4)],'xpos':[(1,5,6),(1,6,2)],'yneg':[(0,4,5),(0,5,1)],'ypos':[(3,2,6),(3,6,7)],'roof':[(4,7,6),(4,6,5)],'bottom':[(0,1,2),(0,2,3)]}
# STL solid regions produce separately named snappy patches (roof is observable).
for name,tris in faces.items():
    text=['solid '+name]
    for tri in tris:
        text+=['facet normal 0 0 0','outer loop']+[f'vertex {verts[i][0]} {verts[i][1]} {verts[i][2]}' for i in tri]+['endloop','endfacet']
    text+=['endsolid '+name]
    (root/'constant/triSurface'/f'{name}.stl').write_text('\n'.join(text)+'\n')
put('system/blockMeshDict',header('dictionary','blockMeshDict','system')+'''convertToMeters 1;
vertices ((-48 -48 0) (136 -48 0) (136 48 0) (-48 48 0) (-48 -48 64) (136 -48 64) (136 48 64) (-48 48 64));
blocks (hex (0 1 2 3 4 5 6 7) (92 48 32) simpleGrading (1 1 1));
edges ();
boundary (
 inlet { type patch; faces ((0 4 7 3)); }
 outlet { type patch; faces ((1 2 6 5)); }
 sideNeg { type symmetryPlane; faces ((0 1 5 4)); }
 sidePos { type symmetryPlane; faces ((3 7 6 2)); }
 ground { type wall; faces ((0 3 2 1)); }
 top { type symmetryPlane; faces ((4 5 6 7)); }
);
mergePatchPairs ();
''')
level=a.level
geom='\n'.join(f'{n}.stl {{type triSurfaceMesh; name {n};}}' for n in faces)
ref='\n'.join(f'{n} {{level ({level} {level}); patchInfo {{type wall;}} }}' for n in faces)
put('system/snappyHexMeshDict',header('dictionary','snappyHexMeshDict','system')+f'''castellatedMesh true; snap true; addLayers false;
geometry {{ {geom} }}
castellatedMeshControls {{ maxLocalCells 1200000; maxGlobalCells 1600000; minRefinementCells 0; maxLoadUnbalance 0.1;
 nCellsBetweenLevels 2; features (); refinementSurfaces {{ {ref} }} refinementRegions {{ }}
 resolveFeatureAngle 30; locationInMesh (-27.31 11.37 15.17); allowFreeStandingZoneFaces true;
}}
snapControls {{ nSmoothPatch 3; tolerance 2; nSolveIter 30; nRelaxIter 5; nFeatureSnapIter 10; implicitFeatureSnap true; explicitFeatureSnap false; multiRegionFeatureSnap false; }}
addLayersControls {{ relativeSizes true; layers {{ }} expansionRatio 1.2; finalLayerThickness 0.3; minThickness 0.1; nGrow 0; featureAngle 60; nRelaxIter 5; nSmoothSurfaceNormals 1; nSmoothNormals 3; nSmoothThickness 10; maxFaceThicknessRatio 0.5; maxThicknessToMedialRatio 0.3; minMedialAxisAngle 90; nBufferCellsNoExtrude 0; nLayerIter 10; nRelaxedIter 5; }}
meshQualityControls {{ #include "meshQualityDict" nSmoothScale 4; errorReduction 0.75; }}
writeFlags (scalarLevels); mergeTolerance 1e-6;
''')
put('system/meshQualityDict', '''maxNonOrtho 65; maxBoundarySkewness 20; maxInternalSkewness 4; maxConcave 80; minVol 1e-13; minTetQuality -1e30; minArea -1; minTwist 0.02; minDeterminant 0.001; minFaceWeight 0.02; minVolRatio 0.01; minTriangleTwist -1; minFlatness -1; minCellDeterminant 0.001;''')
put('system/controlDict',header('dictionary','controlDict','system')+'''application DASimpleFoam; startFrom startTime; startTime 0; stopAt endTime; endTime 50; deltaT 1; writeControl timeStep; writeInterval 9999; purgeWrite 1; writeFormat binary; writePrecision 6; runTimeModifiable false;''')
put('system/fvSchemes',header('dictionary','fvSchemes','system')+'''ddtSchemes {default steadyState;} gradSchemes {default Gauss linear; grad(U) cellLimited Gauss linear 1;} divSchemes {default none; div(phi,U) bounded Gauss linearUpwind grad(U); div(phi,k) bounded Gauss upwind; div(phi,omega) bounded Gauss upwind; div((nuEff*dev2(T(grad(U))))) Gauss linear;} laplacianSchemes {default Gauss linear corrected;} interpolationSchemes {default linear;} snGradSchemes {default corrected;} wallDist {method meshWave;}''')
put('system/fvSolution',header('dictionary','fvSolution','system')+'''solvers { p {solver GAMG; tolerance 1e-8; relTol 0.1; smoother GaussSeidel; maxIter 50;} "(U|k|omega)" {solver smoothSolver; smoother GaussSeidel; tolerance 1e-9; relTol 0.1; maxIter 50;} } SIMPLE {nNonOrthogonalCorrectors 0; consistent no;} relaxationFactors {fields {p 0.3;} equations {"(U|k|omega)" 0.7;}}''')
put('system/decomposeParDict',header('dictionary','decomposeParDict','system')+'''numberOfSubdomains 48; method scotch;''')
put('constant/transportProperties',header('dictionary','transportProperties','constant')+'''transportModel Newtonian; nu [0 2 -1 0 0 0 0] 1.5e-5;''')
put('constant/turbulenceProperties',header('dictionary','turbulenceProperties','constant')+'''simulationType RAS; RAS {RASModel kOmegaSST; turbulence on; printCoeffs on;}''')
patches=('xneg','xpos','yneg','ypos','roof','bottom')
def field(obj, cls, dim, val, inlet, outlet, wall, ground=None):
    b=f' dimensions {dim}; internalField uniform {val}; boundaryField {{\n inlet {{ {inlet} }} outlet {{ {outlet} }}\n "(sideNeg|sidePos|top)" {{type symmetry;}}\n'
    for name in patches:
        b+=f' {name} {{ {ground if name=="bottom" and ground else wall} }}\n'
    b+='}\n'
    put('0/'+obj,header(cls,obj,'0')+b)
field('U','volVectorField','[0 1 -1 0 0 0 0]','(10 0 0)','type atmBoundaryLayerInletVelocity; flowDir (1 0 0); zDir (0 0 1); Uref 10; Zref 8; z0 uniform 0.03; zGround uniform 0; value uniform (10 0 0);','type zeroGradient;','type noSlip;')
field('p','volScalarField','[0 2 -2 0 0 0 0]','0','type zeroGradient;','type fixedValue; value uniform 0;','type zeroGradient;')
field('k','volScalarField','[0 2 -2 0 0 0 0]','0.5','type fixedValue; value uniform 0.5;','type zeroGradient;','type kqRWallFunction; value uniform 0.5;')
field('omega','volScalarField','[0 0 -1 0 0 0 0]','5','type fixedValue; value uniform 5;','type zeroGradient;','type omegaWallFunction; value uniform 5;')
field('nut','volScalarField','[0 2 -1 0 0 0 0]','0.1','type calculated; value uniform 0.1;','type calculated; value uniform 0.1;','type nutUSpaldingWallFunctionDF; value uniform 0;')
print(root, 'level',level,'initial background cells',92*48*32)
