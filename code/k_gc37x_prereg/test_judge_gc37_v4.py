"""v4 synthetic tests (+ one known-bad real obs table: E3 KMPX radar outage, obs only). Never opens a model result."""
import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
import judge_gc37_v4 as j
ST=(39.,-100.)
_ct=j.compare_tier
def _ct_st(*a,**k):
    k.setdefault("station",ST); return _ct(*a,**k)
j.compare_tier=_ct_st

ANCHOR = '2024-05-19T20:40:00'
EVENT = {'station':'RSL','anchor':ANCHOR,'t_obs':'2024-05-19T20:42:00',
         'exist_win':['2024-05-19T17:40:00','2024-05-19T23:40:00'],
         'onset_win':['2024-05-19T14:40:00','2024-05-19T23:40:00']}
FT = {a:[ANCHOR,'2024-05-19T20:30:00','2024-05-19T20:50:00','2024-05-19T23:50:00'] for a in ('AI','GFS','OBS')}
CFG = {'nearest_cell':'nearest_cell_km','time':'time','latitude':'lat','longitude':'lon','area':'area_km2',
       'member':'arm','tier':'tier','first':'first_utc','left':'left',
       'station_lat':'station_lat','station_lon':'station_lon'}

def data():
    obs={'arm':'OBS','tier':64,'time':ANCHOR,'lat':39.,'lon':-100.,'area_km2':100,'nearest_cell_km':5.,
         'station_lat':39.,'station_lon':-100.}
    ai=dict(obs,arm='AI',lon=-99.9)
    gfs=dict(obs,arm='GFS',lon=-99.8)
    frames=[obs,ai,gfs]
    starts={x:{'first_utc':ANCHOR,'left':False} for x in ('AI','GFS','OBS')}
    return frames,starts

class JudgeTests(unittest.TestCase):
    def test_area_sensitivity_when_one_tier_time_none(self):
        frames,onsets=data()
        starts16=copy.deepcopy(onsets)
        starts16['AI']={'first_utc':None,'left':False}
        starts16['GFS']={'first_utc':None,'left':True}
        a=j.compare_tier(EVENT,frames,onsets,64,CFG,FT)
        b=j.compare_tier(EVENT,frames,starts16,16,CFG,FT)
        self.assertEqual((a['verdict'],b['verdict']),('不差于','不判'))
        self.assertEqual(j.combine_areas(a,b),'面积敏感·不判')

    def test_step_sensitivity_even_if_one_combination_undecidable(self):
        self.assertEqual(j.compare_steps('不判','不差于'),'步长敏感·不判')
        self.assertEqual(j.compare_steps('非不差于','不差于'),'步长敏感·不判')

    def test_left_censor_interval_not_a_point(self):
        frames,onsets=data()
        onsets['AI']={'first_utc':None,'left':True}
        onsets['GFS']={'first_utc':'2024-05-19T14:40:00','left':False}
        result=j.compare_tier(EVENT,frames,onsets,64,CFG,FT)
        self.assertEqual(result['time'],'不判')
        self.assertEqual(result['verdict'],'不判')

    def test_right_censor_is_open_and_can_fail(self):
        frames,onsets=data()
        onsets['AI']={'first_utc':None,'left':False}
        result=j.compare_tier(EVENT,frames,onsets,64,CFG,FT)
        self.assertEqual(result['time'],'非不差于')
        self.assertEqual(result['verdict'],'非不差于')
        self.assertTrue(result['time_interval_ai']['lower_open'])

    def test_two_groups_missing_position_does_not_score_position(self):
        frames,onsets=data();frames=[x for x in frames if x['arm']=='OBS']
        result=j.compare_tier(EVENT,frames,onsets,64,CFG,FT)
        self.assertEqual(result['position'],'不判')
        self.assertTrue(result['both_positions_missing'])
        self.assertEqual(result['verdict'],'不判')   # v4 fix (a): v3 returned 不差于 here

    def test_one_group_missing_position_passes_to_existence(self):
        frames,onsets=data();frames=[x for x in frames if x['arm']!='AI']
        result=j.compare_tier(EVENT,frames,onsets,64,CFG,FT)
        self.assertEqual(result['position'],'缺')
        self.assertEqual(result['existence'],'非不差于')
        self.assertEqual(result['verdict'],'非不差于')

    def test_existence_alone_fails_even_when_position_and_time_pass(self):
        frames,onsets=data()
        # GFS object in the existence window; AI anchor object outside it.
        frames=[dict(r,time='2024-05-19T23:50:00') if r['arm']=='AI' else r for r in frames]
        result=j.compare_tier(EVENT,frames,onsets,64,CFG,FT)
        self.assertEqual(result['existence'],'非不差于')
        self.assertEqual(result['verdict'],'非不差于')

    def test_event_config_from_json_and_vote_gate(self):
        path=Path(__file__).resolve().parent.parent/'k_gc37_prereg'/'event_times_gc37.json'
        event=j.load_event(path,'E2')
        self.assertEqual(event['anchor'],ANCHOR)
        self.assertEqual(j.vote_event(['不差于','不差于','不判']),'不差于')
        self.assertEqual(j.vote_event(['非不差于','非不差于','不判']),'差于')
        self.assertEqual(j.vote_combined({'E1':'不差于','E2':'不差于','E3':'不差于'},{'E1':(140,300),'E2':(160,120),'E3':(None,90)}),'值得继续')
        self.assertEqual(j.vote_combined({'E1':'不差于','E2':'不差于'},{'E1':(140,140),'E2':(1,1)}),'不判（样本不足）')

    def test_vote_combined_per_event_24h_clause(self):
        # E1 support fails its own 24 h clause even though E2 passes: 1/3 support -> not 值得继续
        ev={'E1':'不差于','E2':'不差于','E3':'差于'}
        self.assertEqual(j.vote_combined(ev,{'E1':(200,300),'E2':(100,400),'E3':(50,50)}),'不判')
        self.assertEqual(j.vote_combined(ev,{'E1':(100,300),'E2':(100,400),'E3':(50,50)}),'值得继续')
        self.assertEqual(j.vote_combined({'E1':'差于','E2':'差于','E3':'不差于'},{}),'搁置候选')

    def test_anchor_frame_without_object_is_missing_not_borrowed(self):
        frames,onsets=data()
        # AI object only at 20:50 frame; anchor frame 20:40 exists but empty -> position '缺'
        frames=[dict(r,time='2024-05-19T20:50:00') if r['arm']=='AI' else r for r in frames]
        result=j.compare_tier(EVENT,frames,onsets,64,CFG,FT)
        self.assertEqual(result['position'],'缺')

class GateTests(unittest.TestCase):
    def test_gate(self):
        self.assertEqual(j.event_gate({'left_censored':True},True,False,None),'观测不可分辨·首现左删失')
        self.assertEqual(j.event_gate({'left_censored':False},True,True,None),'观测不可分辨·雷达缺测')
        self.assertIsNone(j.event_gate({'left_censored':False},True,False,{'AI':False,'GFS':True}))
        self.assertEqual(j.event_gate({'left_censored':False},True,False,{'AI':False,'GFS':False}),'两组 24 h 均无对象')

class V4Tests(unittest.TestCase):
    def test_both_missing_still_negative_by_existence(self):
        frames,onsets=data()
        # both arms empty at anchor frame; GFS has an object in window (23:40), AI none -> existence NEG stands
        frames=[r for r in frames if r['arm']=='OBS']+[dict(frames[2],time='2024-05-19T23:40:00')]
        r=j.compare_tier(EVENT,frames,onsets,64,CFG,FT)
        self.assertTrue(r['both_positions_missing']); self.assertEqual(r['verdict'],'非不差于')
    def test_obs_left_flag_string_false_is_false(self):
        frames,onsets=data()
        onsets['OBS']={'first_utc':ANCHOR,'left':'False'}
        r=j.compare_tier(EVENT,frames,onsets,64,CFG,FT)
        self.assertEqual(r['time'],'不差于')   # v3 treated the string 'False' as truthy -> 不判
        onsets['OBS']={'first_utc':ANCHOR,'left':'True'}
        self.assertEqual(j.compare_tier(EVENT,frames,onsets,64,CFG,FT)['time'],'不判')
        self.assertIsNone(j.event_gate({'left_censored':'False'},True,False,None))
        self.assertEqual(j.event_gate({'left_censored':'true'},True,False,None),'观测不可分辨·首现左删失')
    def test_station_required_and_used(self):
        frames,onsets=data()
        with self.assertRaises(ValueError): _ct(EVENT,frames,onsets,64,CFG,FT)
        far=dict(frames[1],lon=-97.0); frames.append(far)   # second AI object far from station
        r=_ct(EVENT,frames,onsets,64,CFG,FT,station=(39.,-97.))
        self.assertLess(r['position_distance_km']['AI'],r['position_distance_km']['GFS']+300)
        self.assertGreater(r['position_distance_km']['AI'],200)   # nearest-to-station AI object chosen
    def _cov(self,radars,geo,valid=0.1,n=37,start='2024-05-19T17:40:00'):
        t0=dt.datetime.fromisoformat(start)
        return [{'time_utc':(t0+dt.timedelta(minutes=10*i)).isoformat(),'radars':radars[i] if isinstance(radars,list) else radars,
                 'coverage150_geometric':geo[i] if isinstance(geo,list) else geo,'coverage150_valid_reflectivity':valid} for i in range(n)]
    def test_radar_missing_scan_rule(self):
        cov=self._cov(['KDDC;KICT']*19+['KDDC']*18,1.0)
        self.assertFalse(j.radar_missing(cov,['KDDC','KICT'],EVENT['exist_win'])[0])   # KICT 18/37 missing
        cov=self._cov(['KDDC;KICT']*18+['KDDC']*19,1.0)
        m,d=j.radar_missing(cov,['KDDC','KICT'],EVENT['exist_win']); self.assertTrue(m); self.assertEqual(d['radars_over'],['KICT'])
    def test_radar_missing_geometric_rule_and_valid_ignored(self):
        self.assertFalse(j.radar_missing(self._cov('KDDC',1.0,valid=0.0),['KDDC'],EVENT['exist_win'])[0])  # no echo != missing
        self.assertFalse(j.radar_missing(self._cov('KDDC',[0.7]*18+[0.9]*19),['KDDC'],EVENT['exist_win'])[0])
        self.assertTrue(j.radar_missing(self._cov('KDDC',[0.7]*19+[0.9]*18),['KDDC'],EVENT['exist_win'])[0])
    def test_radar_window_restricted(self):
        cov=self._cov('KDDC',1.0)+self._cov('',0.0,n=10,start='2024-05-20T03:00:00')   # outage after window
        self.assertFalse(j.radar_missing(cov,['KDDC'],EVENT['exist_win'])[0])
        self.assertTrue(j.radar_missing([],['KDDC'],EVENT['exist_win'])[0])
    def test_radar_absent_rows_count_as_missing(self):
        cov=self._cov('KDDC',1.0)
        m,d=j.radar_missing(cov[:18],['KDDC'],EVENT['exist_win']); self.assertTrue(m); self.assertEqual(d['n_frames'],37); self.assertEqual(d['n_rows_absent'],19)
        self.assertFalse(j.radar_missing(cov[:19],['KDDC'],EVENT['exist_win'])[0])
        with self.assertRaises(ValueError): j.radar_missing(cov,[],EVENT['exist_win'])
        with self.assertRaises(ValueError): j.radar_missing(cov+cov[:1],['KDDC'],EVENT['exist_win'])
        bad=[dict(cov[0],time_utc='2024-05-19T17:45:00')]+cov[1:]
        with self.assertRaises(ValueError): j.radar_missing(bad,['KDDC'],EVENT['exist_win'])
    def test_obs_missing_at_anchor_never_pos(self):
        frames,onsets=data(); frames=[r for r in frames if r['arm']!='OBS']
        r=j.compare_tier(EVENT,frames,onsets,64,CFG,FT)
        self.assertTrue(r['obs_missing_at_anchor']); self.assertEqual(r['position'],'不判'); self.assertEqual(r['verdict'],'不判')
        onsets['AI']={'first_utc':None,'left':False}   # time NEG still counts
        self.assertEqual(j.compare_tier(EVENT,frames,onsets,64,CFG,FT)['verdict'],'非不差于')
    def test_arm_distance_kept_when_one_arm_missing(self):
        frames,onsets=data(); frames=[x for x in frames if x['arm']!='AI']
        r=j.compare_tier(EVENT,frames,onsets,64,CFG,FT)
        self.assertIsNone(r['position_distance_km']); self.assertIsNone(r['arm_distance_km']['AI'])
        self.assertAlmostEqual(r['arm_distance_km']['GFS'],j.distance_km(39.,-100.,39.,-99.8),6)
    def test_incomplete_lead_votes(self):
        self.assertEqual(j.vote_event([j.INCOMPLETE,'不差于','不差于']),'不差于')
        self.assertEqual(j.vote_event([j.INCOMPLETE,'非不差于','不差于']),'不判')
    def test_both_missing_time_neg(self):
        frames,onsets=data(); frames=[r for r in frames if r['arm']=='OBS']; onsets['AI']={'first_utc':None,'left':False}
        self.assertEqual(j.compare_tier(EVENT,frames,onsets,64,CFG,FT)['verdict'],'非不差于')
    def test_known_bad_E3_real_obs_table(self):
        import csv
        D=Path('./16_PETW/02_Subprojects/WRF_Modeling/07_Validation/lab_K_gc37_main/readout_24h')
        self.assertTrue(D.exists(), 'readout must be present; this acceptance test may not be skipped')
        ev=j.load_event(Path(__file__).resolve().parent.parent/'k_gc37_prereg'/'event_times_gc37.json','E3')
        sites=[s['site'] for s in json.loads((D/'inventory/sites.json').read_text())['E3']]
        with open(D/'obs/E3_coverage.csv') as fh: cov=list(csv.DictReader(fh))
        m,d=j.radar_missing(cov,sites,ev['exist_win']); self.assertTrue(m); self.assertIn('KMPX',d['radars_over'])
        with open(D/'obs/E1_coverage.csv') as fh: cov1=list(csv.DictReader(fh))
        e1=j.load_event(Path(__file__).resolve().parent.parent/'k_gc37_prereg'/'event_times_gc37.json','E1')
        self.assertFalse(j.radar_missing(cov1,[s['site'] for s in json.loads((D/'inventory/sites.json').read_text())['E1']],e1['exist_win'])[0])
    def test_gate_event_programmatic(self):
        frames,onsets=data(); cov=self._cov('KDDC',1.0)
        g=j.gate_event(EVENT,[frames[0]],{'left_censored':'False'},cov,['KDDC'],CFG)
        self.assertIsNone(g['reason']); self.assertTrue(g['obs_exist150_64'])
        self.assertEqual(j.gate_event(EVENT,[frames[0]],{'left_censored':False},cov,['KDDC'],CFG,{'AI':False,'GFS':False})['reason'],'两组 24 h 均无对象')
        self.assertIsNone(j.gate_event(EVENT,[frames[0]],{'left_censored':False},cov,['KDDC'],CFG,None)['reason'])
        far=dict(frames[0],nearest_cell_km=151.)
        self.assertEqual(j.gate_event(EVENT,[far],{'left_censored':False},cov,['KDDC'],CFG)['reason'],'观测不可分辨·150 km 内无对象')
        self.assertEqual(j.gate_event(EVENT,[frames[0]],{'left_censored':False},cov,['KDDC','KICT'],CFG)['reason'],'观测不可分辨·雷达缺测')

if __name__=='__main__':unittest.main()
