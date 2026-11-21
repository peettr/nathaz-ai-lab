#!/usr/bin/env python3
"""Generate a user solver without writing to the installed v2506 tree."""
from pathlib import Path
import shutil
import sys

src, dst, header = map(Path, sys.argv[1:4])
shutil.copytree(src, dst, ignore=shutil.ignore_patterns('linux*','lnInclude'))
shutil.copyfile(header, dst/'linSysDump.H')

def change(file, old, new):
    p=dst/file
    s=p.read_text()
    if s.count(old)!=1:
        raise RuntimeError(f'Unexpected v2506 source anchor: {p}: {old}')
    p.write_text(s.replace(old, new))

change('pimpleFoam.C', '#include "fvCFD.H"', '#include "fvCFD.H"\n#include "linSysDump.H"')
change('pimpleFoam.C', '    while (runTime.run())', '    int linSolveIndex = 0;\n    while (runTime.run())')
change('pimpleFoam.C', '        ++runTime;', '        ++runTime;\n        linSolveIndex = 0;')
change('pEqn.H', '    pEqn.solve(p.select(pimple.finalInnerIter()));', r'''    const bool linFinal = pimple.finalInnerIter();
    const Foam::word linSelection = p.select(linFinal);
    const char* linFlag = std::getenv("LINSYS_DUMP");
    const bool linEnabled = linFlag && std::string(linFlag) == "1";
    std::string linDir;
    if (linEnabled)
    {
        if (Foam::Pstream::parRun()) throw std::runtime_error("linear system export is serial-only");
        const char* linRoot = std::getenv("LINSYS_ROOT");
        if (!linRoot || !*linRoot) throw std::runtime_error("LINSYS_ROOT required");
        linDir = std::string(linRoot) + "/Solving/PresCorr-" +
            std::to_string(runTime.timeIndex()) + "-" + std::to_string(++linSolveIndex);
        Foam::scalarField d(pEqn.diag());
        Foam::scalarField b(pEqn.source());
        linAddBoundary(pEqn, p, d, b);
        if (::mkdir(linDir.c_str(), 0750)) throw std::runtime_error("cannot create fresh " + linDir);
        linNpy(linDir + "/x_initial.npy", p.primitiveField());
        linDumpMatrix(pEqn, p, d, b, linDir);
        Foam::Info << "LINSYS_BEGIN " << runTime.timeIndex() << " " << linSolveIndex
                   << " " << linSelection << Foam::endl;
    }
    const auto linPerf = pEqn.solve(linSelection);
    if (linEnabled)
    {
        linNpy(linDir + "/x_openfoam.npy", p.primitiveField());
        std::ofstream m(linDir + "/meta.json");
        m << std::setprecision(17)
          << "{\"time\":\"" << runTime.timeName() << "\","
          << "\"step\":" << runTime.timeIndex() << ","
          << "\"correction\":" << linSolveIndex << ","
          << "\"is_final\":" << (linFinal ? "true" : "false") << ","
          << "\"solver_entry\":\"" << linSelection << "\","
          << "\"mesh_moving\":" << (mesh.moving() ? "true" : "false") << ","
          << "\"initial_residual\":" << linPerf.initialResidual() << ","
          << "\"final_residual\":" << linPerf.finalResidual() << ","
          << "\"iterations\":" << linPerf.nIterations() << "}\n";
        m.close();
        if (!m) throw std::runtime_error("cannot write metadata: " + linDir);
    }''')
(dst/'Make'/'files').write_text('pimpleFoam.C\n\nEXE = $(FOAM_USER_APPBIN)/pimpleFoamLinSysDump2506\n')
p=dst/'Make'/'options'
p.write_text(p.read_text().rstrip()+' \\\n    -lz\n')
