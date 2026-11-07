#!/usr/bin/env python3
"""Metadata-free H08 synthetic parity tests; run on Colab CPU with CLIMADA 6.1.0."""
import math, unittest
from rmw_adapter import Node, RadiusUnavailable, fit_rmw, predicted_outer_radius, _h08_profile

class AdapterTests(unittest.TestCase):
    def node(self, radii=None):
        return Node(lat_deg=27, vmax_kt=90, central_hpa=950,
                    environmental_hpa=1010, previous_central_hpa=952,
                    hours_since_previous=6, translation_ms=4,
                    radii_nmi=radii or {})

    def test_h08_synthetic_roundtrip(self):
        true_rmw = 25.0
        node = self.node()
        radii = {k: (predicted_outer_radius(node,true_rmw,k)[0],)*4 for k in (34,50,64)}
        fit = fit_rmw(self.node(radii))
        self.assertLess(abs(fit['rmw_nmi']-true_rmw), 3.0,
                        'prior penalty permits up to 3 nmi recovery error')
        self.assertEqual(fit['thresholds'], [34,50,64])
        for k in radii:
            radius,_ = predicted_outer_radius(self.node(radii),fit['rmw_nmi'],k)
            self.assertLess(abs(radius-radii[k][0])/radii[k][0], 0.08)

    def test_native_angular_profile_parity(self):
        # Compare to CLIMADA directly, not a separately coded B formula.
        import numpy as np
        import xarray as xr
        from climada.hazard.trop_cyclone import trop_cyclone_windfields as wf
        node=self.node(); radial=[25.,50.,100.]
        ours, b=_h08_profile(node,25,radial)
        ds=xr.Dataset(dict(lat=('time',[node.lat_deg,node.lat_deg]),
              cen=('time',[95200.,95000.]), pdelta=('time',[5800.,6000.]),
              rad=('time',[25*1852.,25*1852.]),
              cp=('time',[2*7.29e-5*math.sin(math.radians(27))]*2),
              tstep=('time',[21600.,21600.]),vtrans_norm=('time',[4.,4.])))
        native=wf._compute_angular_windspeeds_h08(ds,
              np.array([radial,radial])*1852.,np.ones((2,3),dtype=bool))[-1]/0.5144444444444445
        np.testing.assert_allclose(ours,native,rtol=1e-12)
        self.assertAlmostEqual(b,float(ds['hol_b'][-1]))

    def test_missing_radii_does_not_impute_prior(self):
        with self.assertRaisesRegex(RadiusUnavailable,'two distinct thresholds'):
            fit_rmw(self.node({34:(80.,90.,70.,75.),50:(0.,0.)}))

    def test_bad_pressure_rejected(self):
        n=self.node({34:(70.,)*4,50:(35.,)*4})
        with self.assertRaisesRegex(RadiusUnavailable,'invalid pressure'):
            fit_rmw(Node(**{**n.__dict__, 'central_hpa':1020}))

if __name__ == '__main__': unittest.main(verbosity=2)
