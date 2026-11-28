#!/usr/bin/env python3
"""Create a fresh OF10 user solver; source solver remains read-only."""
from pathlib import Path
import sys
src, dst, header = map(Path, sys.argv[1:4])
dst.mkdir(parents=True, exist_ok=False)
for f in src.iterdir():
    if f.is_file() and f.suffix in ('.H', '.C'):
        (dst/f.name).write_bytes(f.read_bytes())
(dst/'linSysDump.H').write_bytes(header.read_bytes())
main=(dst/'pimpleFoam.C').read_text()
assert main.count('#include "fvCFD.H"')==1 and main.count('    while (pimple.run(runTime))')==1
main=main.replace('#include "fvCFD.H"','#include "fvCFD.H"\n#include "linSysDump.H"')
main=main.replace('    while (pimple.run(runTime))','    int linSolveIndex = 0;\n    while (pimple.run(runTime))')
main=main.replace('        Info<< "Time = "', '        linSolveIndex = 0;\n        Info<< "Time = "')
(dst/'pimpleFoam.C').write_text(main)
p=(dst/'pEqn.H').read_text()
assert p.count('    pEqn.solve();')==1
p=p.replace('    pEqn.solve();', '''    const bool linEnabled = std::getenv("LINSYS_DUMP") &&
        std::string(std::getenv("LINSYS_DUMP")) == "1";
    std::string linDir;
    auto linStart = std::chrono::steady_clock::now();
    if (linEnabled)
    {
        const char* root = std::getenv("LINSYS_ROOT");
        if (!root) throw std::runtime_error("LINSYS_ROOT required");
        linDir = std::string(root) + "/Solving/PresCorr-" +
            std::to_string(runTime.timeIndex()) + "-" +
            std::to_string(++linSolveIndex);
        linMakeDir(linDir);
        Foam::scalarField d(pEqn.diag());
        Foam::scalarField b(pEqn.source());
        linAddBoundary(pEqn, p, d, b);
        linNpy(linDir + "/x_initial.npy", p.primitiveField());
        linDumpMatrix(pEqn, p, d, b, linDir);
    }
    const Foam::solverPerformance linPerf = pEqn.solve();
    if (linEnabled)
    {
        linNpy(linDir + "/x_openfoam.npy", p.primitiveField());
        const double sec = std::chrono::duration<double>(
            std::chrono::steady_clock::now()-linStart).count();
        std::ofstream m(linDir + "/meta.json");
        m << std::setprecision(17)
          << "{\\\"time\\\":\\\"" << runTime.timeName() << "\\\","
          << "\\\"step\\\":" << runTime.timeIndex() << ","
          << "\\\"correction\\\":" << linSolveIndex << ","
          << "\\\"is_final\\\":" << (pimple.finalNonOrthogonalIter() ? "true" : "false") << ","
          << "\\\"initial_residual\\\":" << linPerf.initialResidual() << ","
          << "\\\"final_residual\\\":" << linPerf.finalResidual() << ","
          << "\\\"iterations\\\":" << linPerf.nIterations() << ","
          << "\\\"export_solve_seconds\\\":" << sec << "}\\n";
        Foam::Info << "LINSYS_EXPORT " << linDir << " seconds=" << sec << Foam::endl;
    }''')
(dst/'pEqn.H').write_text(p)
(dst/'Make').mkdir()
(dst/'Make'/'files').write_text('pimpleFoam.C\n\nEXE = $(FOAM_USER_APPBIN)/pimpleFoamLinSysDump\n')
options=(src/'Make'/'options').read_text()
assert options.rstrip().endswith('-lmeshTools')
(dst/'Make'/'options').write_text(options.rstrip()+' \\\n    -lz\n')
print(dst)
