#!/usr/bin/env python3
"""Stage a fresh stock SPHSimulator build and first static-water gate."""
from pathlib import Path
import shutil

root = Path('/groups/kareem/[用户]/L26_19_TLD_20261111/truth_stock')
source = Path('/groups/kareem/[用户]/L26_19_TLD_20261111/truth_src/source')
assert not root.exists(), 'Never replace an existing run root'
root.mkdir(parents=True)
shutil.copytree(source, root / 'source', symlinks=True)
code = root / 'source/Simulator/SimulatorBase.cpp'
text = code.read_text()
start = text.index('bool SimulatorBase::timeStepNoGUI()')
end = text.index('void SimulatorBase::updateScalarField()', start)
section = text[start:end]
anchor = '\n\treturn true;\n}'
assert section.count(anchor) == 1
instrument = r'''
	// Read-only full-field diagnostics in the stock SPHSimulator stepping loop.
	static unsigned int diagnosticStep = 0;
	++diagnosticStep;
	if (diagnosticStep <= 20)
	{
		for (unsigned int fi = 0; fi < sim->numberOfFluidModels(); ++fi)
		{
			FluidModel *fm = sim->getFluidModel(fi);
			Real minRho = 1.0e30, maxRho = -1.0e30, sumRho = 0.0, maxSpeed = 0.0;
			unsigned int outside = 0;
			for (unsigned int pi = 0; pi < fm->numActiveParticles(); ++pi)
			{
				const Real rho = fm->getDensity(pi);
				const Real speed = fm->getVelocity(pi).norm();
				minRho = std::min(minRho, rho);
				maxRho = std::max(maxRho, rho);
				sumRho += rho;
				maxSpeed = std::max(maxSpeed, speed);
				const Vector3r &pos = fm->getPosition(pi);
				if (std::abs(pos[0]) > 1.5 || pos[1] < 0.0 || pos[1] > 1.5 || std::abs(pos[2]) > 0.25) ++outside;
			}
			std::cout << "STOCK_GATE step=" << diagnosticStep
				<< " t=" << TimeManager::getCurrent()->getTime()
				<< " n=" << fm->numActiveParticles()
				<< " mass0=" << fm->getMass(0)
				<< " rho_min=" << minRho << " rho_max=" << maxRho
				<< " rho_mean=" << (sumRho / fm->numActiveParticles())
				<< " vmax=" << maxSpeed << " outside=" << outside << std::endl;
		}
	}
'''
section = section.replace(anchor, '\n' + instrument + anchor)
text = text[:start] + section + text[end:]
code.write_text(text)
print('stage', root, 'native step instrumentation', code)
# Scene template originates from the checked-in helper, delivered in the same session.
