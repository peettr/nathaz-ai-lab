#!/usr/bin/env python3
"""L26.11 step 2 (A297): square cylinder Re=22000, medium mesh (identical to S1), dt=0.002.
usage: make_case_m.py <outdir> <run: P0|M1|M2|M3>
P0: official IDDESDelta (Δmax), cold start 0 -> 75.8 (10 nominal cycles), shared initial field.
M1: official IDDESDelta (Δmax), restart from P0 t=75.8 -> 606.1 (cold-start counting: discard 0-151.5, window 151.5-606.1).
M2: IDDESDeltaDEScover coupled, hmaxOuter SLADelta,       restart from P0 t=75.8 -> 681.9 (discard 75.8-227.3, window 227.3-681.9).
M3: IDDESDeltaDEScover coupled, hmaxOuter DeltaLiutexTilde, restart from P0 t=75.8 -> 681.9 (same windows as M2).
Base files (mesh, BCs, schemes, solution) are produced by the S1 generator (base_make_case.py, unchanged)."""
import os, sys, subprocess, re
out, run = sys.argv[1], sys.argv[2]
here = os.path.dirname(os.path.abspath(__file__))
END = {'P0': 75.8, 'M1': 606.4, 'M2': 682.2, 'M3': 682.2}[run]   # 10-26 review c5f7676e: align to writeInterval 37900 (analysis windows unchanged)
WSTART = {'P0': None, 'M1': 151.5, 'M2': 227.3, 'M3': 227.3}[run]
# base case from S1 generator (writes 0/, constant/, system/ incl. blockMeshDict, topoSet, fvSchemes, fvSolution)
subprocess.check_call([sys.executable, os.path.join(here, 'base_make_case.py'), out, 'true', str(END), '37900', '0.002', 'libDEScoverDelta_v3'], stdout=subprocess.DEVNULL)   # 10-26: v3 = v2 + corrected Liutex eigen-solver (review c5f7676e MUST-FIX)
tp = os.path.join(out, 'constant/turbulenceProperties')
hdr = open(tp).read().split('simulationType')[0]
if run in ('P0', 'M1'):
    les = """simulationType LES;
LES
{
    LESModel        SpalartAllmarasIDDES;
    turbulence      on;
    printCoeffs     on;
    delta           IDDESDelta;          // official OpenFOAM v2506 IDDES (Delta_outer = Delta_max)
    IDDESDeltaCoeffs
    {
        Cw          0.15;
    }
}
"""
else:
    outer = 'SLADelta' if run == 'M2' else 'DeltaLiutexTilde'
    sub = ("SLADeltaCoeffs\n        {\n            shielding   true;   // v2506 defaults otherwise (FKHmin 0.1, FKHmax 1, a1 0.15, a2 0.3, epsilon 0.01)\n        }"
           if run == 'M2' else "DeltaLiutexTildeCoeffs\n        {\n            deltaCoeff  1.035;\n        }")
    les = f"""simulationType LES;
LES
{{
    LESModel        SpalartAllmarasIDDES;
    turbulence      on;
    printCoeffs     on;
    delta           IDDESDeltaDEScover;  // author's IDDESDelta formula + L26.11 coupling (v2 library), NOT the author's original code
    IDDESDeltaDEScoverCoeffs
    {{
        Cw          0.15;
        fdLimit     0.01;
        Clim        0.15;
        coupled     true;
        hmaxOuter   {outer};
        {sub}
    }}
    IDDESDeltaCoeffs
    {{
        Cw          0.15;
    }}
}}
"""
open(tp, 'w').write(hdr + les)
cd = os.path.join(out, 'system/controlDict'); s = open(cd).read()
if run in ('P0', 'M1'):
    s = s.replace('libs            ("/groups/kareem/[用户]/L26_11_DESCOVER_20261025/lib/libDEScoverDelta_v3.so");\n', '')
s = re.sub(r'purgeWrite\s+0;', 'purgeWrite      2;', s)
# function objects: keep forceCoeffs1 + courant; replace S1 diagnostics with probes + fieldAverage
start = s.index('functions\n{'); s = s[:start]
xs = [0.5625 + 0.0625*i for i in range(56)]          # 0.5625 .. 4.0
zs = [0.25 + 0.5*i for i in range(8)]                  # spanwise
pts = '\n'.join(f'            ({x:.4f} 0 {z:.2f})' for z in zs for x in xs)
fa = '' if WSTART is None else f"""    fieldAverage1
    {{
        type fieldAverage; libs (fieldFunctionObjects);
        timeStart {WSTART}; writeControl writeTime;
        fields ( U {{ mean on; prime2Mean off; base time; }} );
    }}
"""
s += f"""functions
{{
    forceCoeffs1
    {{
        type forceCoeffs; libs (forces); patches (cylinder);
        rho rhoInf; rhoInf 1; CofR (0 0 2);
        liftDir (0 1 0); dragDir (1 0 0); pitchAxis (0 0 1);
        magUInf 1; lRef 1; Aref 4;
        writeControl timeStep; writeInterval 1; log false;
    }}
    centrelineProbes
    {{
        type probes; libs (sampling); fields (U);
        writeControl timeStep; writeInterval 50;
        probeLocations
        (
{pts}
        );
    }}
{fa}    courant {{ type CourantNo; libs (fieldFunctionObjects); writeControl writeTime; }}
}}
"""
open(cd, 'w').write(s)
if run == 'P0':
    # 10-26 P0 (1632187) diverged at step 1-2 from the uniform impulsive start (Co 578, nuTilda blow-up);
    # P0b initialises U with potentialFoam (stock utility). Extra dicts are used only by potentialFoam.
    fs = os.path.join(out, 'system/fvSolution'); t = open(fs).read()
    t = t.replace('solvers\n{', 'solvers\n{\n    Phi { solver GAMG; smoother DIC; tolerance 1e-6; relTol 0.01; }', 1)
    t += "potentialFlow\n{\n    nNonOrthogonalCorrectors 2;\n}\n"
    open(fs, 'w').write(t)
    # 10-26 P0c: P0b at ~1.15 s/step needs ~12 h > h_rt 10 h and wrote nothing before 75.8 (step 37900).
    # Write every 3790 steps (75.8 = 10 x 3790, still aligned with M writeInterval) and allow runtime edits.
    c = open(cd).read()
    c = c.replace('writeInterval   37900;', 'writeInterval   3790;').replace('runTimeModifiable false;', 'runTimeModifiable true;')
    assert 'writeInterval   3790;' in c and 'runTimeModifiable true;' in c
    open(cd, 'w').write(c)
if run != 'P0':
    # restart runs: no 0/ dir needed (fields come from P0 processor*/75.8); keep it out to avoid confusion
    import shutil; shutil.rmtree(os.path.join(out, '0'))
print('written', out, run)
