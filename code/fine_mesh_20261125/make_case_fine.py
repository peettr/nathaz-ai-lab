#!/usr/bin/env python3
"""L26.11 fine mesh (Liang Hu 11-25): case = base_make_case.py output (same domain/BCs/schemes/solver settings as all
L26.11 runs) with ONLY blockMeshDict replaced by the fine design (design_h<h1>_nz<NZ>.json), stock IDDESDelta (Δmax),
and a check-run controlDict (two-stage start, yPlus + wallShearStress + Courant at write time).
usage: make_case_fine.py <outdir> <design.json> <stageA_end> <stageA_dt> <stageB_end> <stageB_dt>"""
import os, sys, json, subprocess, re
out, dj = sys.argv[1], sys.argv[2]
tA, dtA, tB, dtB = map(float, sys.argv[3:7])
here = os.path.dirname(os.path.abspath(__file__))
base = os.path.join(here, '..', 'M', 'scripts', 'base_make_case.py')
subprocess.check_call([sys.executable, base, out, 'false', str(tA), '1000', str(dtA), 'none'], stdout=subprocess.DEVNULL)
d = json.load(open(dj))
def ms(secs):   # multi-grading string ((len n ratio) ...)
    return '(' + ' '.join('(%.6g %d %.6g)' % (L, n, r) for (L, n, r) in secs) + ')'
GX = [ms(g) for g in d['GX']]; GY = [ms(g) for g in d['GY']]
NX, NY, NZ = d['NX'], d['NY'], d['NZ']
bm = open(os.path.join(out, 'system/blockMeshDict')).read()
lines = bm.split('\n'); outl = []; bi = 0
order = [(i, j) for j in range(3) for i in range(3) if (i, j) != (1, 1)]
for l in lines:
    if l.strip().startswith('hex ('):
        i, j = order[bi]; bi += 1
        l = re.sub(r'\) \(\d+ \d+ \d+\) simpleGrading \(.*\)$', ') (%d %d %d) simpleGrading (%s %s 1)' % (NX[i], NY[j], NZ, GX[i], GY[j]), l)
    outl.append(l)
assert bi == 8
open(os.path.join(out, 'system/blockMeshDict'), 'w').write('\n'.join(outl))
tp = os.path.join(out, 'constant/turbulenceProperties'); t = open(tp).read()
hdr = t.split('simulationType')[0]
open(tp, 'w').write(hdr + """simulationType LES;
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
""")
cd = os.path.join(out, 'system/controlDict'); c = open(cd).read()
hdr = c.split('application')[0]
open(cd, 'w').write(hdr + f"""application     pimpleFoam;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         {tA};
deltaT          {dtA};
writeControl    runTime;
writeInterval   {tA};
purgeWrite      0;
writeFormat     binary;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   8;
runTimeModifiable true;
functions
{{
    forceCoeffs1
    {{
        type forceCoeffs; libs (forces); patches (cylinder);
        rho rhoInf; rhoInf 1; CofR (0 0 2);
        liftDir (0 1 0); dragDir (1 0 0); pitchAxis (0 0 1);
        magUInf 1; lRef 1; Aref 4;
        writeControl timeStep; writeInterval 1; log false;
    }}
    yPlus1 {{ type yPlus; libs (fieldFunctionObjects); writeControl writeTime; }}
    wss1 {{ type wallShearStress; libs (fieldFunctionObjects); patches (cylinder); writeControl writeTime; }}
    courant {{ type CourantNo; libs (fieldFunctionObjects); writeControl writeTime; }}
}}
""")
# potentialFoam needs Phi solver + potentialFlow dict (as in make_case_m P0)
fs = os.path.join(out, 'system/fvSolution'); s = open(fs).read()
s = s.replace('solvers\n{', 'solvers\n{\n    Phi { solver GAMG; smoother DIC; tolerance 1e-6; relTol 0.01; }', 1) + "potentialFlow\n{\n    nNonOrthogonalCorrectors 2;\n}\n"
open(fs, 'w').write(s)
json.dump({'stageA': [tA, dtA], 'stageB': [tB, dtB]}, open(os.path.join(out, 'stages.json'), 'w'))
print('written', out, 'cells expected', d['cells'])
