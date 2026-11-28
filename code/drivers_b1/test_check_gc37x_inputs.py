#!/usr/bin/env python3
"""Negative-fixture tests for the frozen input gate; no model verdicts."""
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
from netCDF4 import Dataset
from check_gc37x_inputs import check, GC37, WRF


class InputGateFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def graphcast(self):
        p = self.root / 'tensor.nc'
        with Dataset(p, 'w') as d:
            for name, n in [('batch', 1), ('time', 2), ('level', 37), ('lat', 2), ('lon', 2)]:
                d.createDimension(name, n)
            d.createVariable('level', 'i4', ('level',))[:] = np.arange(1000, 0, -27)[:37]
            for name in GC37:
                v = d.createVariable(name, 'f4', ('batch', 'time', 'level', 'lat', 'lon'))
                if name == 'geopotential':
                    v[:] = np.arange(37)[None, None, :, None, None] * 1000 + 100
                elif name == 'temperature':
                    v[:] = 270
                elif name == 'specific_humidity':
                    v[:] = .001
                else:
                    v[:] = 1
        return p

    def wrfinput(self):
        p = self.root / 'wrfinput.nc'
        with Dataset(p, 'w') as d:
            for name, n in [('Time', 1), ('bottom_top', 3), ('south_north', 2), ('west_east', 3)]:
                d.createDimension(name, n)
            for name in WRF:
                dims = ('Time', 'bottom_top', 'south_north', 'west_east') if name in ('QVAPOR', 'T', 'P', 'PB', 'PH', 'PHB', 'U', 'V') else ('Time', 'south_north', 'west_east')
                v = d.createVariable(name, 'f4', dims)
                if name == 'QVAPOR':
                    v[:] = np.linspace(.001, .005, 6).reshape(1, 1, 2, 3)
                elif name == 'T': v[:] = -10
                elif name == 'PSFC': v[:] = 90000
                else: v[:] = 1
        return p

    def test_graphcast_nan_and_negative_q(self):
        p = self.graphcast()
        self.assertTrue(check(p, 'graphcast')['passed'])
        with Dataset(p, 'a') as d: d.variables['temperature'][0, 0, 0, 0, 0] = np.nan
        self.assertTrue(any('nonfinite' in x for x in check(p, 'graphcast')['errors']))
        with Dataset(p, 'a') as d: d.variables['specific_humidity'][0, 0, 0, 0, 0] = -.001
        self.assertTrue(any('outside_[0,.04]' in x for x in check(p, 'graphcast')['errors']))

    def test_wrf_constant_q_and_nan(self):
        p = self.wrfinput()
        self.assertTrue(check(p, 'wrfinput')['passed'])
        with Dataset(p, 'a') as d: d.variables['QVAPOR'][0, 1, :, :] = 1e-6
        self.assertTrue(any('constant_fake' in x for x in check(p, 'wrfinput')['errors']))
        with Dataset(p, 'a') as d: d.variables['U'][0, 0, 0, 0] = np.nan
        self.assertTrue(any('nonfinite' in x for x in check(p, 'wrfinput')['errors']))


if __name__ == '__main__': unittest.main()
