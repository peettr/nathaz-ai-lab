#!/usr/bin/env python3
"""Synthetic offline unit tests; hand calculations kept adjacent to votes."""
import datetime as dt
import unittest
import numpy as np
import formal_verdict_v1c as v
UTC=dt.timezone.utc

def header(count):
    # NOAA official 1-indexed fixed width: ID 2:12, date 14:26, NUMLEV 33:36.
    a=list(' '*71)
    for start,end,value in [(1,1,'#'),(2,12,'USM00000001'),(14,17,'2024'),
                            (19,20,'06'),(22,23,'15'),(25,26,'00'),(33,36,f'{count:4d}'),
                            (56,62,' 350000'),(64,71,'-0970000')]:
        a[start-1:end]=list(str(value).ljust(end-start+1))
    return ''.join(a)

def level(typ,p,z,t=200,rh=500,dp=50,wd=180,ws=100):
    a=list(' '*51)
    for start,end,value in [(1,1,'1'),(2,2,str(typ)),(4,8,'00000'),(10,15,f'{p*100:6d}'),
                            (16,16,' '),(17,21,f'{z:5d}'),(22,22,' '),
                            (23,27,f'{t:5d}'),(28,28,' '),(29,33,f'{rh:5d}'),
                            (35,39,f'{dp:5d}'),(41,45,f'{wd:5d}'),(47,51,f'{ws:5d}')]:
        a[start-1:end]=list(value)
    return ''.join(a)

def sample(lines): return header(len(lines))+'\n'+'\n'.join(lines)+'\n'

class IGRA(unittest.TestCase):
    def test_two_qualified(self):
        for humidity in (('rh',500),('dp',50)):
            rows=[level(1,1000,200),level(0,975,400),level(0,850,1500),level(0,500,5500),level(0,300,9000)]
            if humidity[0]=='rh': rows[2]=level(0,850,1500,dp=-9999)
            else: rows[2]=level(0,850,1500,rh=-9999)
            s=v.read_igra(sample(rows))[0]
            self.assertTrue(v.qualify_sounding(s)[0]);self.assertAlmostEqual(s['lat'],35)
            self.assertAlmostEqual(s['levels'][0]['p'],1000)
            self.assertAlmostEqual(s['levels'][0]['v'],10)
    def test_two_rejected(self):
        base=[level(1,1000,200),level(0,975,400),level(0,850,1500),level(0,500,5500),level(0,300,9000)]
        x=base.copy();x[2]=level(0,850,1500,rh=-9999,dp=-9999)
        self.assertFalse(v.qualify_sounding(v.read_igra(sample(x))[0])[0])
        y=base.copy();y[1]=level(0,925,800)
        self.assertFalse(v.qualify_sounding(v.read_igra(sample(y))[0])[0])
    def test_truncated(self):
        with self.assertRaises(ValueError):v.read_igra(header(1)+'\n')

class Conservative(unittest.TestCase):
    def test_constant(self):
        a=np.full((2,2),7.)
        self.assertTrue(np.allclose(v.conservative_average(a,[0,1,2],[0,1,2],[0,.5,1,1.5,2],[0,2]),7))
    def test_linear_integral(self):
        # Longitude-linear values 1 and 3 over equal-width native cells.
        # The coarse cell's exact overlap mean is (1+3)/2=2; refining
        # nested grid does not change the area-weighted integral.
        a=np.array([[1.,3.],[1.,3.]])
        coarse=v.conservative_average(a,[0,1,2],[0,1,2],[0,2],[0,2])
        fine=v.conservative_average(a,[0,1,2],[0,1,2],[0,1,2],[0,.5,1,1.5,2])
        self.assertAlmostEqual(coarse[0,0],2)
        self.assertAlmostEqual(np.mean(fine[0]),2)

class DatesAndDistortion(unittest.TestCase):
    def test_anchor_and_lead(self):
        a=dt.datetime(2024,6,15,13,47,tzinfo=UTC)
        self.assertEqual(v.validation_time(a),dt.datetime(2024,6,15,12,tzinfo=UTC))
        self.assertEqual(v.lead_or_censor(a,dt.datetime(2024,6,15,6,tzinfo=UTC)),(6.,None))
        self.assertEqual(v.lead_or_censor(a,dt.datetime(2024,6,15,12,tzinfo=UTC)),(0.,'删失（与初值相同）'))
        self.assertEqual(v.validation_time(dt.datetime(2024,6,15,0,tzinfo=UTC)).hour,0)
    def test_near_zero(self):
        for p,thr in v.NEAR_ZERO.items():
            self.assertEqual(v.x99_and_distortion([thr*.9]*3,[thr*.9]*3,p)['status'],'不判（参照近零）')
            self.assertEqual(v.x99_and_distortion([thr*2]*3,[thr]*3,p)['D'],1.)

class Votes(unittest.TestCase):
    def test_h1_manual_n3_n4_n2(self):
        # n=3: deltas [2,1,-1], 2 positives >=ceil(2n/3)=2;
        # median=1>0 -> conforms. n=4: [1,-1,-2,-3], 1<=floor(4/3)
        # -> nonconforms. n=2: [1,1], below required n=3 -> undecided.
        cases=[({'a':(0,2),'b':(0,1),'c':(1,0)},'符合预期',2),
               (dict(zip('abcd',[(0,1),(1,0),(2,0),(3,0)])),'不符合预期',1),
               ({'a':(0,1),'b':(0,1)},'不判',2),
               (dict(zip('abcd',[(0,1),(0,1),(1,0),(1,0)])),'不判',2)]
        for data,verdict,votes in cases:
            got=v.h1(data);self.assertEqual(got['verdict'],verdict);self.assertEqual(got['positive'],votes)
    def test_h2_manual_n3_n4_n2(self):
        # n=3 paired errors AI/GFS -> [2,1,-1], 2>=ceil(2)=2 => AI larger.
        # n=4 deltas [-1,-2,3,4], 2<ceil(8/3)=3 either direction => equal.
        # n=2 [-1,-2] -> undecided, despite both favoring AI.
        cases=[(dict(zip('abc',[(3,1),(2,1),(1,2)])),'AI 较大'),
               (dict(zip('abcd',[(1,2),(1,3),(4,1),(5,1)])),'相当'),
               ({'a':(1,2),'b':(1,3)},'不判'),
               (dict(zip('abcd',[(1,2),(1,3),(1,4),(4,1)])),'AI 较小')]
        for data,verdict in cases:self.assertEqual(v.h2(data)['verdict'],verdict)
        self.assertEqual(v.h2(cases[0][0],'极值失真 D')['reference_bias'],'参照偏向 GFS 组')
    def test_cohorts_separate(self):
        rows=[dict(cohort='main',event='N1',group='AI',parameter='MLCAPE',lead=24,status='删失（缺文件）'),
              dict(cohort='secondary',event='E1',group='GFS',parameter='MLCAPE',lead=24,status='LCL 超顶记 0')]
        result=v.report_by_cohort(rows)
        self.assertEqual(result['main']['censor_counts']['删失（缺文件）'],1)
        self.assertEqual(result['secondary']['censor_counts']['删失（缺文件）'],0)
        self.assertEqual(result['secondary']['censor_counts']['LCL 超顶记 0'],1)
    def test_pearson_only(self):
        self.assertAlmostEqual(v.pearson_report([1,2,3],[2,4,6]),1)
        self.assertIsNone(v.pearson_report([1,1,1],[2,3,4]))
if __name__=='__main__':unittest.main(verbosity=2)
