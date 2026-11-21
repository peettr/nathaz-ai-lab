#!/usr/bin/env python3
"""Patch a copied Foundation OF10 pimpleFoam (never modify system source)."""
from pathlib import Path
import sys

src, dst, header = map(Path, sys.argv[1:4])
dst.mkdir(parents=True, exist_ok=False)
for name in ('pimpleFoam.C', 'pEqn.H', 'createFields.H', 'UEqn.H', 'setRDeltaT.H', 'correctPhi.H'):
    (dst/name).write_bytes((src/name).read_bytes())
(dst/'linSysDump.H').write_bytes(header.read_bytes())
main = (dst/'pimpleFoam.C').read_text()
main = main.replace('#include "fvCFD.H"', '#include "fvCFD.H"\n#include "linSysDump.H"')
main = main.replace('    while (pimple.run(runTime))', '    int linSolveIndex = 0;\n    while (pimple.run(runTime))')
assert 'int linSolveIndex = 0;' in main
(dst/'pimpleFoam.C').write_text(main)
p = (dst/'pEqn.H').read_text()
old = '    pEqn.solve();'
replacement = '''    // Only the explicitly opted-in five steps export; the control uses the same
    // solver and all numerical settings in the on/off paired runs.
    const bool linEnabled = std::getenv("LINSYS_DUMP") &&
                            std::string(std::getenv("LINSYS_DUMP")) == "1";
    std::string linDir;
    auto linStart = std::chrono::steady_clock::now();
    if (linEnabled)
    {
        const char* root = std::getenv("LINSYS_ROOT");
        if (!root) throw std::runtime_error("LINSYS_ROOT required");
        const std::string step = std::to_string(runTime.timeIndex());
        linDir = std::string(root) + "/Solving/PresCorr-" + step + "-" +
                 std::to_string(++linSolveIndex);
        linMakeDir(linDir);
        Foam::scalarField d(pEqn.diag());
        Foam::scalarField b(pEqn.source());
        forAll(pEqn.internalCoeffs(), patchi)
        {
            const Foam::labelUList& addr = pEqn.lduAddr().patchAddr(patchi);
            const Foam::scalarField& ic = pEqn.internalCoeffs()[patchi];
            const Foam::scalarField& bc = pEqn.boundaryCoeffs()[patchi];
            forAll(addr, j)
            {
                d[addr[j]] += ic[j];
                if (!p.boundaryField()[patchi].coupled()) b[addr[j]] += bc[j];
                else throw std::runtime_error("serial-only dump: coupled boundary");
            }
        }
        linNpy(linDir + "/x_initial.npy", p.primitiveField());
        linDumpMatrix(pEqn, d, b, linDir);
    }
    const Foam::solverPerformance linPerf = pEqn.solve();
    if (linEnabled)
    {
        linNpy(linDir + "/x_openfoam.npy", p.primitiveField());
        const double sec = std::chrono::duration<double>(
            std::chrono::steady_clock::now()-linStart).count();
        std::ofstream m(linDir + "/meta.json");
        m << std::setprecision(17)
          << "{\\"time\\":\\"" << runTime.timeName() << "\\","
          << "\\"step\\":" << runTime.timeIndex() << ","
          << "\\"correction\\":" << linSolveIndex << ","
          << "\\"is_final\\":" << (pimple.finalNonOrthogonalIter() ? "true" : "false") << ","
          << "\\"initial_residual\\":" << linPerf.initialResidual() << ","
          << "\\"final_residual\\":" << linPerf.finalResidual() << ","
          << "\\"iterations\\":" << linPerf.nIterations() << ","
          << "\\"export_solve_seconds\\":" << sec << "}\\n";
        Foam::Info << "LINSYS_EXPORT " << linDir << " seconds=" << sec << Foam::endl;
    }'''
assert p.count(old) == 1
(dst/'pEqn.H').write_text(p.replace(old,replacement))
(dst/'Make').mkdir()
(dst/'Make'/'files').write_text('pimpleFoam.C\n\nEXE = $(FOAM_USER_APPBIN)/pimpleFoamLinSysDump\n')
options=(src/'Make'/'options').read_text()
assert options.rstrip().endswith('-lmeshTools')
(dst/'Make'/'options').write_text(options.rstrip()+' \\\n    -lz\n')
print(dst)
