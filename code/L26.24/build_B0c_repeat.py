#!/usr/bin/env python3
"""Build B0c OpenFOAM-10 native repeated-pressure timer in a fresh root."""
from pathlib import Path
import sys
import shutil
src, dst = map(Path, sys.argv[1:3])
assert src.is_dir() and not dst.exists()
dst.mkdir(parents=True)
for f in src.iterdir():
    if f.is_file() and f.suffix in ('.C', '.H'):
        shutil.copy2(f, dst / f.name)
p = dst / 'pEqn.H'
s = p.read_text()
a = s.index('    const auto b0_begin =')
b = s.index('\n    if (pimple.finalNonOrthogonalIter())', a)
replacement = r'''    const bool b0cSmoke = std::getenv("B0C_SMOKE") != nullptr;
    const bool b0cSelected = b0cSmoke
        ? (runTime.value() > 0 && runTime.value() < 0.00051)
        : (runTime.value() > 44.0125 && runTime.value() <= 44.015001);
    if (b0cSelected)
    {
        // fvMatrix::solve() selects pFinal on the last PIMPLE correction.
        const Foam::dictionary taControls
        (
            mesh.solution().solverDict
            (
                p.select
                (
                    !mesh.schemes().steady()
                 && mesh.data::lookupOrDefault<bool>("finalIteration", false)
                )
            )
        );
        Foam::dictionary tbControls(taControls);
        tbControls.set("tolerance", Foam::scalar(1e-8));
        tbControls.set("relTol", Foam::scalar(0));
        const Foam::scalarField savedPsi(p.primitiveField());
        for (int tier = 0; tier < (b0cSmoke ? 1 : 2); ++tier)
        {
            const Foam::dictionary& controls = tier == 0 ? taControls : tbControls;
            for (int rep = 1; rep <= 5; ++rep)
            {
                p.primitiveFieldRef() = savedPsi;
                p.correctBoundaryConditions();
                const auto started = std::chrono::steady_clock::now();
                const Foam::solverPerformance perf = pEqn.solve(controls);
                Foam::scalar seconds = std::chrono::duration<double>
                    (std::chrono::steady_clock::now() - started).count();
                Foam::reduce(seconds, Foam::maxOp<Foam::scalar>());
                if (Foam::Pstream::master())
                {
                    std::ofstream out(std::getenv("B0C_CSV"), std::ios::app);
                    if (!out) throw std::runtime_error("B0C_CSV open failed");
                    out << std::setprecision(17) << "later," << runTime.timeName()
                        << ',' << (b0SolveIndex + 1) << ',' << (tier == 0 ? "Ta" : "Tb")
                        << ',' << Foam::Pstream::nProcs() << ',' << rep
                        << ',' << perf.initialResidual() << ',' << perf.finalResidual()
                        << ',' << perf.nIterations() << ',' << seconds << '\n';
                }
            }
        }
        p.primitiveFieldRef() = savedPsi;
        p.correctBoundaryConditions();
    }
    // Exactly one ordinary Ta solve advances the CFD trajectory.
    const Foam::solverPerformance b0c_advance = pEqn.solve();
    ++b0SolveIndex;
'''
s = s[:a] + replacement + s[b:]
p.write_text(s)
main = dst / 'pimpleFoam.C'
s = main.read_text()
assert 'int b0SolveIndex = 0;' in s
main.write_text(s)
(dst / 'Make').mkdir()
(dst / 'Make' / 'files').write_text('pimpleFoam.C\n\nEXE = $(FOAM_USER_APPBIN)/pimpleFoamB0cRepeat\n')
shutil.copy2(src / 'Make' / 'options', dst / 'Make' / 'options')
print(dst)
