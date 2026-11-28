#!/usr/bin/env python3
"""Generate OF10 B0 native pressure timer from the frozen D0 source copy."""
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
a = s.index('    const bool linEnabled =')
b = s.index('\n    if (pimple.finalNonOrthogonalIter())', a)
s = s[:a] + '''    const auto b0_begin = std::chrono::steady_clock::now();
    const Foam::solverPerformance b0_perf = pEqn.solve();
    Foam::scalar b0_seconds = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - b0_begin).count();
    Foam::reduce(b0_seconds, Foam::maxOp<Foam::scalar>());
    if (Foam::Pstream::master())
    {
        std::ofstream b0_file(std::getenv("B0_CSV"), std::ios::app);
        if (!b0_file) throw std::runtime_error("B0_CSV open failed");
        b0_file << std::setprecision(17) << std::getenv("B0_SEGMENT")
                << ',' << runTime.timeName() << ',' << ++b0SolveIndex
                << ',' << std::getenv("B0_TIER") << ',' << Foam::Pstream::nProcs()
                << ',' << b0_perf.initialResidual()
                << ',' << b0_perf.finalResidual()
                << ',' << b0_perf.nIterations()
                << ',' << b0_seconds << '\\n';
    }
''' + s[b:]
p.write_text(s)
main = destination / 'pimpleFoam.C'
s = main.read_text()
assert s.count('#include "fvCFD.H"') == 1
assert s.count('    while (pimple.run(runTime))') == 1
assert s.count('        linSolveIndex = 0;') == 1
s = s.replace('#include "fvCFD.H"', '#include "fvCFD.H"\n#include "PstreamReduceOps.H"\n#include <chrono>\n#include <fstream>\n#include <iomanip>\n#include <cstdlib>\n#include <stdexcept>')
s = s.replace('    while (pimple.run(runTime))', '    int b0SolveIndex = 0;\n    while (pimple.run(runTime))')
s = s.replace('        linSolveIndex = 0;', '        linSolveIndex = 0;\n        b0SolveIndex = 0;')
main.write_text(s)
(destination / 'Make').mkdir()
(destination / 'Make' / 'files').write_text('pimpleFoam.C\n\nEXE = $(FOAM_USER_APPBIN)/pimpleFoamB0Timer\n')
(destination / 'Make' / 'options').write_bytes((source / 'Make' / 'options').read_bytes())
print(destination)
