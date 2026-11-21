"""CM1 E5 selection kernel; callers must provide actual radar/HRRR reflectivity.

No station-peak proxy: the anchor must be the first >=35 dBZ scan near the station.
Observed lowest-elevation radar reflectivity must be mapped to the grid by caller;
reflectivity must come from the closest volume scan to the chosen analysis hour.
This kernel never downloads datasets or asserts a real case passed QC.
"""
from datetime import datetime, timedelta, timezone
import numpy as np


def analysis_hour(anchor_utc):
    """Latest integral UTC hour no later than anchor minus 45 minutes."""
    if anchor_utc.tzinfo is None:
        raise ValueError('anchor must be timezone-aware')
    t = anchor_utc.astimezone(timezone.utc) - timedelta(minutes=45)
    return t.replace(minute=0, second=0, microsecond=0)


def distance_km(lat1, lon1, lat2, lon2):
    """Great-circle distance, including longitude wraparound."""
    a, b, c, d = map(np.deg2rad, (lat1, lon1, lat2, lon2))
    x = np.sin((c-a)/2)**2 + np.cos(a)*np.cos(c)*np.sin((d-b)/2)**2
    return 6371.0088*2*np.arcsin(np.sqrt(np.clip(x, 0, 1)))


def select_column(station_lat, station_lon, lat, lon, land,
                  observed_dbz, simulated_dbz, *, coverage=None):
    """Return nearest eligible (y,x), or None. All arrays same 2D HRRR grid.

    Reflectivity/coverage must cover every cell within 20 km of candidates;
    missing values fail closed, not interpreted as echo-free. Observed field
    must be real lowest-elevation radar, not HRRR or model-derived echo.
    land=True denotes HRRR LAND=1, not a coast-distance heuristic.
    """
    lat, lon, land, observed_dbz, simulated_dbz = map(np.asarray,
        (lat, lon, land, observed_dbz, simulated_dbz))
    if not all(a.shape == lat.shape for a in (lon, land, observed_dbz, simulated_dbz)) or lat.ndim != 2:
        raise ValueError('2D arrays must have the same shape')
    if coverage is None:
        coverage = np.ones(lat.shape, dtype=bool)
    coverage = np.asarray(coverage)
    if coverage.shape != lat.shape:
        raise ValueError('coverage shape mismatch')
    station_d = distance_km(station_lat, station_lon, lat, lon)
    for y, x in sorted(zip(*np.where((station_d <= 50) & (land == 1))),
                       key=lambda pos: station_d[pos]):
        near = distance_km(lat[y,x], lon[y,x], lat, lon) <= 20
        if not np.all(coverage[near]):
            continue
        obs, sim = observed_dbz[near], simulated_dbz[near]
        if np.all(np.isfinite(obs)) and np.all(np.isfinite(sim)) and np.all(obs < 20) and np.all(sim < 20):
            return (int(y), int(x))
    return None


if __name__ == '__main__':
    import unittest
    class Tests(unittest.TestCase):
        def test_hour(self):
            a = datetime(2023, 7, 3, 21, 16, tzinfo=timezone.utc)
            self.assertEqual(analysis_hour(a), datetime(2023, 7, 3, 20, tzinfo=timezone.utc))
        def test_land_echo_missing(self):
            lat = np.array([[0.,0.,0.,0.]])
            lon = np.array([[0.,.17,.34,.51]]) # ~19 km intervals
            land = np.array([[0,1,1,1]])
            obs = np.zeros((1,4)); sim = obs.copy()
            # station at first cell: water rejected; second land selected
            self.assertEqual(select_column(0,0,lat,lon,land,obs,sim),(0,1))
            obs[0,0] = 25
            # second within 20km of echo, third clean (40km from echo)
            self.assertEqual(select_column(0,0,lat,lon,land,obs,sim),(0,2))
            obs[0,2] = np.nan
            self.assertIsNone(select_column(0,0,lat,lon,land,obs,sim))
    unittest.main()
