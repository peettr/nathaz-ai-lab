"""Frozen-rule GC37 event judgement. No model files are opened by this module.

Input contract: `frames` is a list of object rows with configurable column names;
objects are filtered by arm/tier/area. `onsets` maps arm to first_utc/left
under configured column names. A row's station coordinates are supplied by the
station/observation table (not hard-coded to Akron). Times are naive UTC ISO.
"""
import datetime as dt
import json
import math
from pathlib import Path

POS, NEG, UNKNOWN = '不差于', '非不差于', '不判'

def load_event(path, key):
    return json.loads(Path(path).read_text(encoding='utf-8'))[key]

def minutes(value, base):
    return (dt.datetime.fromisoformat(value) - dt.datetime.fromisoformat(base)).total_seconds()/60

def distance_km(a, b, c, d):
    a,c=math.radians(a),math.radians(c)
    dl=math.radians(d-b)
    h=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin(dl/2)**2
    return 6371.229*2*math.asin(min(1.,math.sqrt(h)))

def nearest_frame_objects(rows, arm, tier, anchor, fields, station):
    eligible=[r for r in rows if r[fields['member']]==arm and int(r[fields['tier']])==int(tier)
              and float(r[fields['area']])>=tier]
    if not eligible: return None
    closest=min(abs(minutes(r[fields['time']],anchor)) for r in eligible)
    eligible=[r for r in eligible if abs(minutes(r[fields['time']],anchor))==closest]
    return min(eligible,key=lambda r: distance_km(station[0],station[1],float(r[fields['latitude']]),float(r[fields['longitude']])))

def onset_interval(info, event, fields):
    base=event['anchor']
    if info.get(fields['left']) in (True,'True','true',1):
        return {'lo':-math.inf,'hi':minutes(event['onset_win'][0],base),'lower_open':False,'upper_open':False}
    if info.get(fields['first']):
        t=minutes(info[fields['first']],base)
        return {'lo':t,'hi':t,'lower_open':False,'upper_open':False}
    return {'lo':minutes(event['onset_win'][1],base),'hi':math.inf,'lower_open':True,'upper_open':False}

def abs_bounds(interval, obs):
    lo,hi=interval['lo'],interval['hi']
    minimum=0 if lo<=obs<=hi else min(abs(lo-obs),abs(hi-obs))
    maximum=max(abs(lo-obs),abs(hi-obs))
    return minimum,maximum

def compare_time(a, g, o):
    # Strictly all admissible left-/right-censored values must agree.
    al,au=abs_bounds(a,o);gl,gu=abs_bounds(g,o)
    if au<=gl+60:return POS
    if al>gu+60:return NEG
    # Equal open lower endpoint is also a strict failure if GFS upper is fixed.
    if al==gu+60 and a['lower_open'] and math.isfinite(gu):return NEG
    return UNKNOWN

def compare_tier(event, frames, onsets, tier, fields):
    station_rows=[r for r in frames if fields['station_lat'] in r and fields['station_lon'] in r]
    if not station_rows: raise ValueError('station coordinates required')
    station=(float(station_rows[0][fields['station_lat']]),float(station_rows[0][fields['station_lon']]))
    nearest={arm:nearest_frame_objects(frames,arm,tier,event['anchor'],fields,station) for arm in ('AI','GFS','OBS')}
    obs=nearest['OBS'];a=nearest['AI'];g=nearest['GFS']
    def in_window(arm):
        lo,hi=map(dt.datetime.fromisoformat,event['exist_win'])
        return any(r[fields['member']]==arm and int(r[fields['tier']])==int(tier)
                   and float(r[fields['area']])>=tier and lo<=dt.datetime.fromisoformat(r[fields['time']])<=hi
                   and distance_km(station[0],station[1],float(r[fields['latitude']]),float(r[fields['longitude']]))<=150
                   for r in frames)
    exists={arm:in_window(arm) for arm in ('AI','GFS')}
    existence=NEG if exists['GFS'] and not exists['AI'] else POS
    position=UNKNOWN;distances=None
    if obs is not None and a is not None and g is not None:
        distances={arm:distance_km(float(obs[fields['latitude']]),float(obs[fields['longitude']]),
                  float(nearest[arm][fields['latitude']]),float(nearest[arm][fields['longitude']])) for arm in ('AI','GFS')}
        position=POS if distances['AI']<=distances['GFS']+50 else NEG
    elif (a is None) != (g is None): position='缺'
    ai_iv=onset_interval(onsets['AI'],event,fields);g_iv=onset_interval(onsets['GFS'],event,fields)
    obs_info=onsets['OBS']
    if obs_info.get(fields['left']) or not obs_info.get(fields['first']):time=UNKNOWN
    else: time=compare_time(ai_iv,g_iv,minutes(obs_info[fields['first']],event['anchor']))
    verdict=NEG if existence==NEG or position==NEG or time==NEG else (POS if time==POS else UNKNOWN)
    return {'tier_km2':tier,'position':position,'position_distance_km':distances,
            'existence':existence,'exists_150km':exists,'time':time,
            'time_interval_ai':{'lower_open':ai_iv['lower_open'],'lo':ai_iv['lo'],'hi':ai_iv['hi']},
            'verdict':verdict}

def combine_areas(a,b):
    av,bv=a['verdict'],b['verdict']
    if av==bv:return av
    return '面积敏感·不判'

def compare_steps(formal, appendix):
    return formal if formal==appendix else '步长敏感·不判'

def vote_event(verdicts):
    if verdicts.count(POS)>=2:return POS
    if verdicts.count(NEG)>=2:return '差于'
    return UNKNOWN

def vote_combined(events, positions_24h_km):
    determined=[v for v in events.values() if v!=UNKNOWN]
    if len(determined)<3:return '不判（样本不足）'
    if determined.count(POS)<2:return '不值得继续'
    if not any(p is not None and p<=150 for p in positions_24h_km):return '不值得继续'
    return '值得继续'
