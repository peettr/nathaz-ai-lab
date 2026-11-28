#!/usr/bin/env python3
"""Synthetic pipeline-only tests; no fixture is an ABL measurement."""
import copy, json, math, unittest
from assert_T17 import evaluate, USTAR, FORCE, H, KAPPA, Z0

def case(shift=0):
    u={str(k):USTAR/KAPPA*math.log((k-.5+Z0)/Z0)*(1+shift) for k in range(1,65)}
    return {'v0_attempts':[[{'momentum':100,'tau_x':1,'ustar':USTAR},{'momentum':101,'tau_x':1.01,'ustar':USTAR*1.01}]],
            'stress':{'rho':1.2,'tau_x_time_mean':1.2*FORCE*H},
            'blocks':[{'k_res_z9p5':USTAR**2*.65,'u_k3':u['3'],
                       'u_x_mean_z9p5':u['10'],'u_x_variance_z9p5':.01} for _ in range(4)],
            'correlations':{'rx_half':.03,'ry_half':-.02},'profile_u':u}

def base():return {'schema':'T17-B-v1','cases':{g:{s:case() for s in ('1','2')} for g in ('bounce','t4','t15')}}

class FrozenGates(unittest.TestCase):
    def test_target_met(self):
        r=evaluate(base());self.assertEqual(set(r['group_verdicts'].values()),{'达标'})
        self.assertEqual(r['pairwise']['t4__t15']['verdict'],'在本指标下未检出差异')
        self.assertIn('rc-review',r['case_E_link'])
    def test_fail_science(self):
        d=base();d['cases']['bounce']['1']=case(.16)
        self.assertEqual(evaluate(d)['group_verdicts']['bounce'],'未达标')
    def test_unbalanced_after_three_extensions(self):
        d=base();c=d['cases']['bounce']['1'];c['v0_attempts']=[[{'momentum':100,'tau_x':1,'ustar':1},{'momentum':120,'tau_x':1,'ustar':1}]]*4
        r=evaluate(d);self.assertEqual(r['group_verdicts']['bounce'],'不判');self.assertIn('未平衡',r['cases']['bounce']['1']['invalid_reasons'])
    def test_turbulence_invalid(self):
        d=base();d['cases']['bounce']['1']['blocks'][0]['k_res_z9p5']=USTAR**2*.45
        self.assertIn('湍流未维持',evaluate(d)['cases']['bounce']['1']['invalid_reasons'])
    def test_domain_invalid(self):
        d=base();d['cases']['bounce']['1']['correlations']['ry_half']=.101
        self.assertIn('域长不足',evaluate(d)['cases']['bounce']['1']['invalid_reasons'])
    def test_stress_invalid(self):
        d=base();d['cases']['bounce']['1']['stress']['tau_x_time_mean']*=.90
        self.assertIn('S1/V1应力不一致',evaluate(d)['cases']['bounce']['1']['invalid_reasons'])
    def test_distinguishable_and_case_e(self):
        d=base()
        for s in ('1','2'):d['cases']['t4'][s]=case(.08)
        r=evaluate(d);self.assertEqual(r['pairwise']['t4__t15']['verdict'],'可辨')
        self.assertIn('符合',r['case_E_link'])
        self.assertEqual(len(r['pairwise']['t4__t15']['noise_six']),6)
    def test_mixed_seed_cancels(self):
        d=base();d['cases']['t4']['1']=case(.08);d['cases']['t4']['2']=case(-.08)
        r=evaluate(d);self.assertEqual(r['pairwise']['t4__t15']['verdict'],'在本指标下未检出差异')
        self.assertFalse(r['pairwise']['t4__t15']['same_sign'])
    def test_invalid_group_has_no_pair(self):
        d=base();d['cases']['t15']['1']['correlations']['rx_half']=.2
        self.assertEqual(evaluate(d)['pairwise']['t4__t15']['verdict'],'不判')
    def test_wrong_profile_rejected(self):
        d=base();del d['cases']['t4']['2']['profile_u']['64']
        with self.assertRaises(ValueError):evaluate(d)
    def test_nonfinite_rejected(self):
        d=base();d['cases']['t4']['2']['profile_u']['3']=float('nan')
        with self.assertRaises(ValueError):evaluate(d)
    def test_s3_staggered_gradient(self):
        r=evaluate(base());self.assertLess(r['cases']['t4']['1']['S3']['max_abs_difference'],.01)
        self.assertEqual(len(r['cases']['t4']['1']['S3']['differences_by_z']),7)

if __name__=='__main__':unittest.main(verbosity=2)
