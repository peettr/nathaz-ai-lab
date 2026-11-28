#!/usr/bin/env python3
"""Generate a v2506 simpleFoam user solver from a verified parent exporter."""
from pathlib import Path
import hashlib
import shutil
import sys

PARENT_SHA256 = 'd62af6763e6934b0f871215477c780d2836cb3e38dc74399d8acdd5d7fccaf15'
HOOK = r'''        const char* linFlag = std::getenv("LINSYS_DUMP");
        const bool linEnabled = linFlag && std::string(linFlag) == "1";
        const auto linCorrection = ++linSolveIndex;
        std::string linDir;
        Foam::word linSelection;
        bool linSymmetric = false;
        if (linEnabled)
        {
            if (Foam::Pstream::parRun()) throw std::runtime_error("linear system export is serial-only");
            const char* linRoot = std::getenv("LINSYS_ROOT");
            if (!linRoot || !*linRoot) throw std::runtime_error("LINSYS_ROOT required");
            linSelection = p.select(p.mesh().data().isFinalIteration());
            linSymmetric = static_cast<const Foam::lduMatrix&>(pEqn).symmetric();
            linDir = std::string(linRoot) + "/Solving/PresCorr-" +
                std::to_string(runTime.timeIndex()) + "-" + std::to_string(linCorrection);
            Foam::scalarField d(pEqn.diag());
            Foam::scalarField b(pEqn.source());
            linAddBoundary(pEqn, p, d, b);
            if (::mkdir(linDir.c_str(), 0750)) throw std::runtime_error("cannot create fresh " + linDir);
            linNpy(linDir + "/x_initial.npy", p.primitiveField());
            linDumpMatrix(pEqn, p, d, b, linDir);
            Foam::Info << "LINSYS_BEGIN " << runTime.timeIndex() << " " << linCorrection
                       << " " << linSelection << Foam::endl;
        }
        const auto linPerf = pEqn.solve();
        if (linEnabled)
        {
            linNpy(linDir + "/x_openfoam.npy", p.primitiveField());
            std::ofstream m(linDir + "/meta.json");
            m << std::setprecision(17)
              << "{\"time\":\"" << runTime.timeName() << "\","
              << "\"step\":" << runTime.timeIndex() << ","
              << "\"simple_iteration\":" << runTime.timeIndex() << ","
              << "\"correction\":" << linCorrection << ","
              << "\"is_final\":null,\"is_final_note\":\"稳态 SIMPLE 无 final 语义\","
              << "\"symmetric\":" << (linSymmetric ? "true" : "false") << ","
              << "\"solver_entry\":\"" << linSelection << "\","
              << "\"initial_residual\":" << linPerf.initialResidual() << ","
              << "\"final_residual\":" << linPerf.finalResidual() << ","
              << "\"iterations\":" << linPerf.nIterations() << "}\n";
            m.close();
            if (!m) throw std::runtime_error("cannot write metadata: " + linDir);
        }'''


def generate(src, dest, header):
    if hashlib.sha256(header.read_bytes()).hexdigest() != PARENT_SHA256:
        raise ValueError('unexpected parent exporter digest')
    edits = {
        'simpleFoam.C': [('#include "fvCFD.H"', '#include "fvCFD.H"\n#include "linSysDump.H"'),
                         ('    while (simple.loop())\n    {', '    while (simple.loop())\n    {\n        Foam::label linSolveIndex = 0;')],
        'pEqn.H': [('        pEqn.solve();', HOOK)],
    }
    patched = {}
    for name, pairs in edits.items():
        text = (src/name).read_text()
        for old, new in pairs:
            if text.count(old) != 1:
                raise ValueError(f'changed source anchor: {name}: {old}')
            text = text.replace(old, new)
        patched[name] = text
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns('linux*', 'lnInclude'))
    shutil.copyfile(header, dest/'linSysDump.H')
    for name, text in patched.items():
        (dest/name).write_text(text)
    (dest/'Make'/'files').write_text('simpleFoam.C\n\nEXE = $(FOAM_USER_APPBIN)/simpleFoamLinSysDump2506\n')
    p = dest/'Make'/'options'
    p.write_text(p.read_text().rstrip() + ' \\\n    -lz\n')


if __name__ == '__main__':
    generate(*map(Path, sys.argv[1:]))
