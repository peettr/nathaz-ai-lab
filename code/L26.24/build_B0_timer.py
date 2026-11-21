#!/usr/bin/env python3
"""Generate a native OF10 pimpleFoam timing probe in a fresh destination.

No CFD execution here. Timing probe measures native pressure solve only, not
exported-matrix replay; any resulting systems must be explicitly marked unpaired.
"""
import sys
from pathlib import Path

source, destination = map(Path, sys.argv[1:3])
assert source.is_dir() and not destination.exists()
destination.mkdir(parents=True)
for f in source.iterdir():
    if f.is_file() and f.suffix in ('.C', '.H'):
        (destination / f.name).write_bytes(f.read_bytes())
p = destination / 'pEqn.H'
s = p.read_text()
assert s.count('    pEqn.solve();') == 1
s = s.replace('    pEqn.solve();', '''    const auto b0_begin = std::chrono::steady_clock::now();
    const Foam::solverPerformance b0_perf = pEqn.solve();
    const auto b0_end = std::chrono::steady_clock::now();
    Foam::Info << "B0_PRESSURE time=" << runTime.timeName()
               << " rankCount=" << Foam::Pstream::nProcs()
               << " solveIndex=" << ++b0SolveIndex
               << " initial=" << b0_perf.initialResidual()
               << " final=" << b0_perf.finalResidual()
               << " iterations=" << b0_perf.nIterations()
               << " seconds=" << std::chrono::duration<double>(b0_end-b0_begin).count()
               << Foam::endl;''')
p.write_text(s)
main = destination / 'pimpleFoam.C'
s = main.read_text()
assert s.count('#include "fvCFD.H"') == 1
assert s.count('    while (pimple.run(runTime))') == 1
assert s.count('        Info<< "Time = "') == 1
s = s.replace('#include "fvCFD.H"', '#include "fvCFD.H"\n#include <chrono>')
s = s.replace('    while (pimple.run(runTime))', '    int b0SolveIndex = 0;\n    while (pimple.run(runTime))')
s = s.replace('        Info<< "Time = "', '        b0SolveIndex = 0;\n        Info<< "Time = "')
main.write_text(s)
(destination / 'Make').mkdir()
(destination / 'Make' / 'files').write_text('pimpleFoam.C\n\nEXE = $(FOAM_USER_APPBIN)/pimpleFoamB0Timer\n')
(destination / 'Make' / 'options').write_bytes((source / 'Make' / 'options').read_bytes())
print(destination)
