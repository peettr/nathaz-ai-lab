import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from rmw_adapter_v3 import Node, fit_series, fit_rmw, prior_nmi

T=datetime(2024,9,26,tzinfo=timezone.utc)
def node(thresholds=(34,50),vmax=90,lat=30):
    return Node(lat,vmax,960,1010,965,6,4,{k:(70,72,0,0) for k in thresholds})

class TestLevels(unittest.TestCase):
    def test_primary_two_thresholds(self):
        with patch('rmw_adapter_v3.fit_rmw',return_value={'rmw_nmi':35,'thresholds':[34,50]}):
            x=fit_series([T],[node()]);self.assertEqual(x[0]['tier'],1)
    def test_single_threshold_and_prior_weight(self):
        with patch('rmw_adapter_v3.fit_rmw',return_value={'rmw_nmi':40,'thresholds':[34]}) as f:
            x=fit_series([T],[node((34,))],prior_weight=1)
            self.assertEqual(x[0]['tier'],2);self.assertEqual(f.call_args.kwargs['prior_weight'],1)
    def test_temporal_log_interpolation_and_single_side(self):
        ts=[T+timedelta(hours=h) for h in (0,6,12,26)]
        ns=[node(),node(()),node(),node(())]
        with patch('rmw_adapter_v3.fit_rmw',side_effect=[{'rmw_nmi':20},{'rmw_nmi':80}]):
            x=fit_series(ts,ns)
        self.assertAlmostEqual(x[1]['rmw_nmi'],40);self.assertEqual(x[1]['tier'],3)
        self.assertEqual(x[3]['tier'],4)  # beyond 12h
        with patch('rmw_adapter_v3.fit_rmw',return_value={'rmw_nmi':20}):
            x=fit_series([T,T+timedelta(hours=10)],[node(),node(())]);self.assertEqual(x[1]['rmw_nmi'],20)
    def test_climatology_bounds(self):
        x=fit_series([T],[node((),lat=30)])[0]
        self.assertEqual(x['tier'],4);self.assertAlmostEqual(x['rmw_nmi'],prior_nmi(90,30))
        self.assertEqual(fit_series([T],[node((),lat=10000)])[0]['rmw_nmi'],200)
    def test_window_sensitivity(self):
        ts=[T,T+timedelta(hours=14)]
        with patch('rmw_adapter_v3.fit_rmw',return_value={'rmw_nmi':33}):
            x=fit_series(ts,[node(),node(())],hours=18);self.assertEqual(x[1]['tier'],3)
    def test_real_h08_single_threshold(self):
        result=fit_rmw(node((34,)),min_thresholds=1)
        self.assertEqual(result['thresholds'],[34]);self.assertTrue(5<=result['rmw_nmi']<=200)

if __name__=='__main__':unittest.main(verbosity=2)
