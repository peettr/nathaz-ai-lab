# Verbatim excerpts from community_wind_simulation.py
# original lines 122-143
def make_bounds(xmin, xmax, ymin, ymax, hmax, inmult, outmult, sidmult, inlet: str):
    """
    Return x0, x1, y0, y1 with padding rules:

        inlet   : 5 * Hmax upstream
        outlet  : 15 * Hmax downstream
        lateral : ±5 * Hmax
        top     : handled elsewhere (always 15 * Hmax)
    """
    if inlet == "W":            # flow +x
        x0, x1 = xmin - inmult*hmax, xmax + outmult*hmax
        y0, y1 = ymin - sidmult*hmax, ymax + sidmult*hmax
    elif inlet == "E":          # flow –x
        x0, x1 = xmin - outmult*hmax, xmax + inmult*hmax
        y0, y1 = ymin - sidmult*hmax, ymax + sidmult*hmax
    elif inlet == "S":          # flow +y
        x0, x1 = xmin - sidmult*hmax, xmax + sidmult*hmax
        y0, y1 = ymin - inmult*hmax, ymax + outmult*hmax
    else:                       # inlet == "N"  (flow –y)
        x0, x1 = xmin - sidmult*hmax, xmax + sidmult*hmax
        y0, y1 = ymin - outmult*hmax, ymax + inmult*hmax
    return x0, x1, y0, y1

# original lines 203-246
def write_bmd(x0,x1,y0,y1,z0,z1,nx,ny,nz,side_type,out:Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    if side_type == "cyclic":
        side1 = "side1  { type cyclic; neighbourPatch side2; faces ((0 1 5 4)); }"
        side2 = "side2  { type cyclic; neighbourPatch side1; faces ((2 3 7 6)); }"
    else:
        side1 = "side1  { type patch; faces ((0 1 5 4)); }"
        side2 = "side2  { type patch; faces ((2 3 7 6)); }"

    txt=f"""
    /*--------------------------------*- C++ -*----------------------------------*\\
    | =========                 |                                                 |
    | \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
    |  \\    /   O peration     | Version:  10                                    |
    |   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
    |    \\/     M anipulation  |                                                 |
    \\*---------------------------------------------------------------------------*/
    FoamFile{{\n version 2.0;\n format ascii;\n class dictionary;\n object blockMeshDict;}}
    convertToMeters 1.0;

    vertices
    (
     ({x0} {y0} {z0}) ({x1} {y0} {z0}) ({x1} {y1} {z0}) ({x0} {y1} {z0})
     ({x0} {y0} {z1}) ({x1} {y0} {z1}) ({x1} {y1} {z1}) ({x0} {y1} {z1})
    );

    blocks
    (
     hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)
    );

    boundary
    (
     inlet   {{ type patch; faces ((0 4 7 3)); }}
     outlet  {{ type patch; faces ((1 2 6 5)); }}
     {side1}
     {side2}
     top     {{ type patch; faces ((4 5 6 7)); }}
     ground  {{ type wall;  faces ((0 3 2 1)); }}
    );

    mergePatchPairs();
    """
    out.write_text(txt)

# original lines 258-394
TEMPLATE = textwrap.dedent("""
/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  10                                 |
|   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile {{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      snappyHexMeshDict;
}}


castellatedMesh on;
snap            on;
addLayers       off;

geometry
{{
    ROI
    {{
        type triSurfaceMesh;
        file "{roi_stl}.stl";
    }}
    Surrounding
    {{
        type triSurfaceMesh;
        file "{sur_stl}.stl";
    }}
{geometry_entries}
}};

castellatedMeshControls
{{
    maxLocalCells 100000000;
    maxGlobalCells 2000000000;
    minRefinementCells 10;
    maxLoadUnbalance 0.10;
    nCellsBetweenLevels {ncellblvl};
    resolveFeatureAngle 30;

    features
    (
        {{ file "{roi_stl}.eMesh";          level {roi_feat_level}; }}
        {{ file "{sur_stl}.eMesh";  level {sur_feat_level}; }}
    );

    refinementSurfaces
    {{
        ROI
        {{
            level ({roi_level} {roi_level});
            patchInfo {{ type wall; }}
        }}
        Surrounding
        {{
            level ({sur_level} {sur_level});
            patchInfo {{ type wall; }}
        }}
    }}

    refinementRegions
    {{
{refinement_entries}
    }}
    insidePoint (0.01 0.01 0.01);
    allowFreeStandingZoneFaces false;
}}

snapControls
{{
    nSmoothPatch 3;
    tolerance 2.0;
    nSolveIter 30;
    nRelaxIter 5;
    nFeatureSnapIter 10;
    implicitFeatureSnap false;
    explicitFeatureSnap true;
    multiRegionFeatureSnap false;
}}

meshQualityControls
{{
     maxNonOrtho 65;

    //- Max skewness allowed. Set to <0 to disable.
    maxBoundarySkewness 20;
    
    maxInternalSkewness 4;

    //- Max concaveness allowed. Is angle (in degrees) below which concavity
    //  is allowed. 0 is straight face, <0 would be convex face.
    //  Set to 180 to disable.
    maxConcave 80;

    //- Minimum projected area v.s. actual area. Set to -1 to disable.
    minFlatness 0.5;

    //- Minimum cell pyramid volume relative to min bounding box length^3
    //  Set to a fraction of the smallest cell volume expected.
    //  Set to very negative number (e.g. -1e30) to disable.
    minVol -1e30;

    minTetQuality 1e-30;

    //- Minimum face twist. Set to <-1 to disable. dot product of face normal
    //  and face centre triangles normal
    minTwist 0.02;

    //- Minimum normalised cell determinant
    //  1 = hex, <= 0 = folded or flattened illegal cell
    minDeterminant 0.001;

    //- minFaceWeight (0 -> 0.5)
    minFaceWeight 0.02;

    //- minVolRatio (0 -> 1)
    minVolRatio 0.01;

    // Advanced

    //- Number of error distribution iterations
    nSmoothScale 4;
    //- Amount to scale back displacement at error points
    errorReduction 0.75;
    
    minArea  0;

    minTriangleTwist  0;
}}
debug 0;
mergeTolerance 1e-6;
""")

# original lines 465-493
TP_RANSkwSST = textwrap.dedent("""
/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  10                                 |
|   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile{
    version 2.0;
    format ascii;
    class dictionary;
    object turbulenceProperties;
}

simulationType RAS;

RAS
{
    RASModel kOmegaSST;
    turbulence on;
    printCoeffs on;
    delta cubeRootVol;
    cubeRootVolCoeffs
	{
    		deltaCoeff      1;
	}
}
""")

# original lines 717-757
def body_U_meanABL(side, Uref, Href, z0):
    return textwrap.dedent(f"""
        /*--------------------------------*- C++ -*----------------------------------*\\
        | =========                 |                                                 |
        | \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
        |  \\    /   O peration     | Version:  10                                 |
        |   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
        |    \\/     M anipulation  |                                                 |
        \\*---------------------------------------------------------------------------*/
        FoamFile
        {{
            version     2.0;
            format      ascii;
            class       volVectorField;
            location    "0";
            object      U;
        }}
        dimensions      [0 1 -1 0 0 0 0];
        internalField   uniform (0 0 0);
        boundaryField
        {{
            inlet
            {{
                type atmBoundaryLayerInletVelocity;
                Uref {Uref};
                Zref {Href};
                zDir (0 0 1);
                flowDir (1 0 0);
                z0 uniform {z0};
                zGround uniform 0;
                value uniform ({Uref} 0 0);
            }}
            outlet {{ type pressureInletOutletVelocity; value uniform (0 0 0); }}
            side1  {{ type {side}; }}
            side2  {{ type {side}; }}
            top    {{ type slip; }}
            ground        {{ type fixedValue; value uniform (0 0 0); }}
            ROI           {{ type fixedValue; value uniform (0 0 0); }}
            Surrounding   {{ type fixedValue; value uniform (0 0 0); }}
        }}
    """)

# original lines 801-841
def body_k(side, Uref, Href, z0):
    return textwrap.dedent(f"""
        /*--------------------------------*- C++ -*----------------------------------*\\
        | =========                 |                                                 |
        | \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
        |  \\    /   O peration     | Version:  10                                 |
        |   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
        |    \\/     M anipulation  |                                                 |
        \\*---------------------------------------------------------------------------*/
        FoamFile
        {{
            version     2.0;
            format      ascii;
            class       volScalarField;
            location    "0";
            object      k;
        }}
        dimensions      [0 2 -2 0 0 0 0];
        internalField   uniform 0.06;
        boundaryField
        {{
            inlet
            {{
                type atmBoundaryLayerInletK;
                Uref {Uref};
                Zref {Href};
                zDir (0 0 1);
                flowDir (1 0 0);
                z0 uniform {z0};
                zGround uniform 0;
                value uniform 0.06;
            }}
            outlet {{ type zeroGradient; }}
            side1 {{ type {side}; }}
            side2 {{ type {side}; }}
            top   {{ type slip; }}
            ground        {{ type kqRWallFunction; value $internalField; }}
            ROI           {{ type kqRWallFunction; value $internalField; }}
            Surrounding   {{ type kqRWallFunction; value $internalField; }}
        }}
    """)

# original lines 923-975
def body_omega(side,Uref,Href,z0):
    return textwrap.dedent(f"""
        /*--------------------------------*- C++ -*----------------------------------*\\
        | =========                 |                                                 |
        | \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
        |  \\    /   O peration     | Version:  10                                 |
        |   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
        |    \\/     M anipulation  |                                                 |
        \\*---------------------------------------------------------------------------*/
        FoamFile
        {{
            version     2.0;
            format      ascii;
            class       volScalarField;
            location    "0";
            object      epsilon;
        }}
        dimensions      [0 0 -1 0 0 0 0];
        internalField   uniform 100;
        boundaryField
        {{
            inlet
            {{
                type codedFixedValue;
                value uniform 100;
                name  omegaCoded;
                code
                #{{
                    const scalar Bs = 0.09;
                    const fvPatch& patch = this->patch();
                    const vectorField& cf = patch.Cf();
                    scalarField& field = *this;
                    forAll(cf,i)
                    {{
                        field[i] = {Uref}/(sqrt(Bs)*(cf[i].z()+{z0})*{math.log((Href+z0)/z0)});
                    }}
                #}};
            }}
            outlet {{ type zeroGradient; }}
            side1 {{ type {side}; }}
            side2 {{ type {side}; }}
            top   {{ type slip; }}
            ground        {{ type 	 omegaWallFunction;
	                         blended true;
	                         value 	$internalField; }}
            ROI           {{ type 	 omegaWallFunction;
	                         blended true;
	                         value 	$internalField; }}
            Surrounding   {{ type 	 omegaWallFunction;
	                         blended true;
	                         value 	$internalField; }}
        }}
    """)

# original lines 977-1037
def body_nut(side, ground_style, z0, Uref, Href, roi_style, surround_style):
    if ground_style == "rough":
        gf = f"type nutkAtmRoughWallFunction;\n        z0 uniform {z0};\n        value uniform 0;"
    else:
        gf = ("type nutkWallFunction;\n        Cmu 0.09;\n        kappa 0.42;\n"
              "        E 9.793;\n        value uniform 0;")
    

    if roi_style == "rough":
        rf = f"type nutkAtmRoughWallFunction;\n        z0 uniform {z0};\n        value uniform 0;"
    else:
        rf = ("type nutkWallFunction;\n        Cmu 0.09;\n        kappa 0.42;\n"
              "        E 9.793;\n        value uniform 0;")
    

    if surround_style == "rough":
        sf = f"type nutkAtmRoughWallFunction;\n        z0 uniform {z0};\n        value uniform 0;"
    else:
        sf = ("type nutkWallFunction;\n        Cmu 0.09;\n        kappa 0.42;\n"
              "        E 9.793;\n        value uniform 0;")
    

    return textwrap.dedent(f"""
        /*--------------------------------*- C++ -*----------------------------------*\\
        | =========                 |                                                 |
        | \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
        |  \\    /   O peration     | Version:  10                                 |
        |   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
        |    \\/     M anipulation  |                                                 |
        \\*---------------------------------------------------------------------------*/
        FoamFile
        {{
            version     2.0;
            format      ascii;
            class       volScalarField;
            location    "0";
            object      nut;
        }}
        dimensions      [0 2 -1 0 0 0 0];
        internalField   uniform 5e-05;
        boundaryField
        {{
            Uref {Uref};
            Zref {Href};
            zDir (0 0 1);
            flowDir (1 0 0);
            z0 uniform {z0};
            zGround uniform 0;
            Cmu 0.09;
            kappa 0.41;
            value uniform 0.09;
            inlet  {{ type calculated; value uniform 0; }}
            outlet {{ type calculated; value uniform 0; }}
            side1  {{ type {side}; }}
            side2  {{ type {side}; }}
            top    {{ type slip; }}
            ground        {{ {gf} }}
            ROI           {{ {rf} }}
            Surrounding   {{ {sf} }}
        }}
    """)

# original lines 1039-1068
P_BODY = """
/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  10                                 |
|   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
     {
         version     2.0;
         format      ascii;
         class       volScalarField;
         location    "0";
         object      p;
     }
dimensions [0 2 -2 0 0 0 0];
internalField uniform 0;
boundaryField
{
    inlet  { type zeroGradient; }
    outlet { type fixedValue; value uniform 0; }
    side1  { type %s; }
    side2  { type %s; }
    top    { type slip; }
    ground        { type zeroGradient; }
    ROI           { type zeroGradient; }
    Surrounding   { type zeroGradient; }
}
"""

# original lines 1070-1070
SIDE_MAP = {"cyclic": "cyclic", "slip": "slip"}

# original lines 1074-1125
TP_RANSC = textwrap.dedent("""\
    /*--------------------------------*- C++ -*----------------------------------*\\
    | =========                 |                                                 |
    | \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
    |  \\    /   O peration     | Version:  10                                    |
    |   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
    |    \\/     M anipulation  |                                                 |
    \\*---------------------------------------------------------------------------*/
    FoamFile
    {{
        version 2.0;
        format  ascii;
        class   dictionary;
        location "system";
        object  controlDict;
    }}

    application  simpleFoam;

    startFrom latestTime;
                          
    startTime 0;
    
    stopAt endTime;
    
    endTime {end_T};  

    deltaT {deltaT_sim};
    
    writeControl timeStep;

    writeInterval {deltaT_write};
    
    purgeWrite 0;
    
    writeFormat ascii;

    writePrecision 6;
    
    writeCompression compressed;
    
    timeFormat general;

    timePrecision 6;

    runTimeModifiable true;

    libs ("libatmosphericModels.so");

    

""")

# original lines 1190-1208
TP_PROFILE  = textwrap.dedent("""\
    {ProfileName}
    {{
        type            probes;
        libs ("libsampling.so");
                                
        writeControl   timeStep;                          
        writeInterval  {N_profile};
        timeStart {t_start};
                                
        fields          ({fields});

        probeLocations
        (
            {points}
        );
    }}
                             
""")

# original lines 1210-1240
TP_PLANE  = textwrap.dedent("""\
    {PlaneName}
    {{
        type            surfaces;
        libs ("libsampling.so");
                                
        writeControl   timeStep;                          
        writeInterval  {N_plane};
        timeStart {t_start};
        timeEnd {t_end};

        surfaceFormat   	vtk;                             
        fields          ({fields});
        
        interpolationScheme cellPoint;

        surfaces
        (
            sectionPlane
            {{
                type cuttingPlane;
                planeType pointAndNormal;
                point {plane_point};
                normal {plane_normal};
                interpolate true;
            }}
        );
    }}
                                
    
""")

# original lines 1244-1265
TP_transportProperty = textwrap.dedent("""
/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  10                                 |
|   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version 2.0;
    format  ascii;
    class   dictionary;
    location "constant";
    object  transportProperties;
}}

transportModel  Newtonian;

nu              [0 2 -1 0 0 0 0] {nu};

""")

# original lines 1281-1303
TP_surfFeat = textwrap.dedent("""
/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  www.OpenFoam.org
    \\  /    A nd           | Version:  10
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    object      surfaceFeaturesDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

surfaces  ("Surrounding.stl" "ROI.stl");
#includeEtc "caseDicts/surface/surfaceFeaturesDict.cfg"

// ************************************************************************* //


""")

# original lines 1305-1373
TP_fvSch_RANS = textwrap.dedent("""
/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  www.OpenFoam.org
    \\  /    A nd           | Version:  10
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSchemes;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

ddtSchemes
{
    default         steadyState;
}

gradSchemes
{
    default         cellLimited Gauss linear 0.5;
}

divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss linearUpwindV grad(U);
    div(phi,k)      bounded Gauss upwind; 
    div(phi,epsilon) bounded Gauss upwind;
    div(phi,omega)  bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}

laplacianSchemes
{
    default         Gauss linear limited 0.5;
}

interpolationSchemes
{
    default         linear;
    interpolate(U)  linear;
}

snGradSchemes
{
    default         limited 0.5;
}

fluxRequired
{
    default         no;
    p               ;
}

wallDist
{
    method meshWave;
}

// ************************************************************************* //


""")

# original lines 1445-1581
TP_fvSol_RANS = textwrap.dedent("""
/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  www.OpenFoam.org
    \\  /    A nd           | Version:  10
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSolution;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solvers
{
    p                                  // linear equation system solver for p
    {
        solver          GAMG;           // very efficient multigrid solver
        tolerance       1e-09;          // solver finishes if either absolute
        relTol          0.001;          // tolerance is reached or the relative
                                        // tolerance here
        minIter         3;              // a minimum number of iterations
        maxIter         100;            // limitation of iterions number
        smoother        DIC;            // setting for GAMG
        nPreSweeps      1;              // 1 for p, set to 0 for all other!
        nPostSweeps     2;              // 2 is fine
        nFinestSweeps   2;              // 2 is fine
        scaleCorrection true;           // true is fine
        directSolveCoarsestLevel false; // false is fine
        cacheAgglomeration on;          // on is fine; set to off, if dynamic
                                        // mesh refinement is used!
        nCellsInCoarsestLevel 500;      // 500 is fine,
                                        // otherwise sqrt(number of cells)
        agglomerator    faceAreaPair;   // faceAreaPair is fine
        mergeLevels     1;              // 1 is fine
    }

    U                                   // linear equation system solver for U
    {
        solver          smoothSolver;   // solver type
        smoother        GaussSeidel;    // smoother type
        tolerance       1e-09;          // solver finishes if either absolute
        relTol          0.001;           // tolerance is reached or the relative
                                        // tolerance here
        nSweeps         1;              // setting for smoothSolver
        maxIter         100;            // limitation of iterations number
    }

    k
    {
        solver          smoothSolver;   // solver type
        smoother        GaussSeidel;    // smoother type
        tolerance       1e-09;          // solver finishes if either absolute
        relTol          0.001;           // tolerance is reached or the relative
                                        // tolerance here
        nSweeps         1;              // setting for smoothSolver
        maxIter         100;            // limitation of iterations number
    }

    epsilon
    {
        solver          smoothSolver;   // solver type
        smoother        GaussSeidel;    // smoother type
        tolerance       1e-09;          // solver finishes if either absolute
        relTol          0.001;           // tolerance is reached or the relative
                                        // tolerance here
        nSweeps         1;              // setting for smoothSolver
        maxIter         100;            // limitation of iterations number
    }

    omega
    {
        solver          smoothSolver;   // solver type
        smoother        GaussSeidel;    // smoother type
        tolerance       1e-09;          // solver finishes if either absolute
        relTol          0.001;           // tolerance is reached or the relative
                                        // tolerance here
        nSweeps         1;              // setting for smoothSolver
        maxIter         100;            // limitation of iterations number
    }

    R
    {
        solver          PBiCG;
        preconditioner  DILU;
        tolerance       1e-06;
//        relTol          0.1;
	relTol          0.001;
    }

    nuTilda
    {
        solver          PBiCG;
        preconditioner  DILU;
        tolerance       1e-06;
//        relTol          0.1;
	relTol          0.001;
    }
}

SIMPLE
{
    nNonOrthogonalCorrectors 0;

    residualControl
    {
        p               1e-6;
        U               1e-6;
        "(k|epsilon|omega)" 1e-6;
    }
}

potentialFlow
{
	nNonOrthogonalCorrectors 3;
}

relaxationFactors
{
    p               0.3;
    U               0.7;
    k               0.7;
    epsilon         0.7;
    omega           0.7;
    R               0.7;
    nuTilda         0.7;
}

// ************************************************************************* //


""")

