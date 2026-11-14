#!/usr/bin/env python3
"""Prepare isolated native SPHSimulator static-water scenes, no solver computation."""
import json
from pathlib import Path

ROOT = Path('/groups/kareem/[用户]/L26_19_TLD_20261111/truth_stock')
MESH = '/groups/kareem/[用户]/L26_19_TLD_20261111/truth_src/source/data/models/UnitBox.obj'
for label, height in [('H1', .30), ('H2', .60)]:
    scene = {
        'Configuration': {
            'particleRadius': .035, 'simulationMethod': 4,
            'boundaryHandlingMethod': 0, 'gravitation': [0, -9.81, 0],
            'timeStepSize': .001, 'cflMethod': 0, 'stopAt': .019,
            'pause': False, 'dataExportFPS': 1000,
            'enablePartioExport': False, 'particleAttributes': 'velocity;density',
            'DFSPH': {'minIterations': 2, 'maxIterations': 100,
                      'maxError': .05, 'maxIterationsV': 100,
                      'maxErrorV': .1, 'enableDivergenceSolver': True}
        },
        'Materials': [{'id': 'Fluid', 'density0': 1000,
                       'viscosityMethod': 1,
                       'Standard viscosity': {'viscosity': 1e-6}}],
        'RigidBodies': [{'geometryFile': MESH, 'translation': [0, .75, 0],
                         'rotationAxis': [1, 0, 0], 'rotationAngle': 0,
                         'scale': [3, 1.5, .5], 'isDynamic': False,
                         'isWall': True, 'samplingMode': 1}],
        'FluidBlocks': [{'denseMode': 0,
                         'start': [-1.465, .035, -.215],
                         'end': [1.465, height - .035, .215]}]
    }
    path = ROOT / ('scene_' + label + '.json')
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(scene, indent=2) + '\n')
    print(path)
