"""Synthetic-only regression tests; never open a GC37 model result."""
import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
import judge_gc37_v2 as j

ANCHOR = '2024-05-19T20:40:00'
EVENT = {'station':'RSL','anchor':ANCHOR,'t_obs':'2024-05-19T20:42:00',
         'exist_win':['2024-05-19T17:40:00','2024-05-19T23:40:00'],
         'onset_win':['2024-05-19T14:40:00','2024-05-19T23:40:00']}
FT = {a:[ANCHOR,'2024-05-19T20:30:00','2024-05-19T20:50:00','2024-05-19T23:50:00'] for a in ('AI','GFS','OBS')}
CFG = {'time':'time','latitude':'lat','longitude':'lon','area':'area_km2',
       'member':'arm','tier':'tier','first':'first_utc','left':'left',
       'station_lat':'station_lat','station_lon':'station_lon'}

def data():
    obs={'arm':'OBS','tier':64,'time':ANCHOR,'lat':39.,'lon':-100.,'area_km2':100,
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
        self.assertEqual(result['verdict'],'不差于')

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
        path=Path(__file__).with_name('event_times_gc37.json')
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

if __name__=='__main__':unittest.main()
