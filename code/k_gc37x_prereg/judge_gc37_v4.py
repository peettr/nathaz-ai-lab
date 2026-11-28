"""Frozen-rule GC37 event judgement. v4 11-23 (expansion B, plan 扩样方案_GC37_20261122.md §3 item 5/1/6; delegation #6b5f6254):
  (a) position not judged (both model arms missing at the anchor frame, OR obs has no object at the anchor frame) -> cell
      cannot be POS (prereg §6 "三条同时满足"/"两组都缺 -> 位置不判"; §8 不判); NEG from existence/time still stands;
      [review d2a48efe: v3/v4-draft let obs-missing pass as POS];
  (a2) per-arm distance arm_distance_km is computed whenever OBS and that arm have an object (for the 24 h absolute
      position clause, which needs "至少一组"); the position verdict itself still needs all three;
  (b) every left_censored flag parsed by as_bool() (string "False" was truthy in v3 compare_tier);
  (c) compare_tier(station=...) takes ONE station coordinate pair (runner passes events_selected values) instead of row columns;
  (d) radar_missing() = data-missing definition (supplementary rule B1) on the FULL 10-min frame grid of the existence window
      (absent rows = all radars missing, geometric 0); exists_in_window(); gate_event() for programmatic gating.
  All thresholds and other logic identical to v3 (sha256 46dc4e28...).
Previous: (v3 11-16: existence uses nearest_cell_km per K; v2 11-16: nearest-frame and vote_combined aligned to prereg text). No model files are opened by this module.

Input contract: `frames` is a list of object rows with configurable column names;
objects are filtered by arm/tier/area. `onsets` maps arm to first_utc/left
under configured column names. Station coordinates are passed as station=(lat,lon)
(events file values). 'Nearest to station' = object centroid great-circle distance. Times are naive UTC ISO.
"""
import datetime as dt
import json
import math
from pathlib import Path

POS, NEG, UNKNOWN = '不差于', '非不差于', '不判'
INCOMPLETE = '不判（积分不可完成）'

def as_bool(v):
    """v4: uniform boolean parsing of CSV/JSON flags."""
    if isinstance(v, str): return v.strip().lower() in ('true', '1', 'yes')
    return bool(v) if v is not None else False

def load_event(path, key):
    return json.loads(Path(path).read_text(encoding='utf-8'))[key]

def minutes(value, base):
    return (dt.datetime.fromisoformat(value) - dt.datetime.fromisoformat(base)).total_seconds()/60

def distance_km(a, b, c, d):
    a,c=math.radians(a),math.radians(c)
    dl=math.radians(d-b)
    h=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin(dl/2)**2
    return 6371.229*2*math.asin(min(1.,math.sqrt(h)))

def nearest_frame_objects(rows, arm, tier, anchor, fields, station, frame_times=None):
    """Prereg sec.6 position: take the output frame closest to the anchor among ALL
    output frames of this arm (frame_times[arm]); if that frame has no qualifying
    object, return None ('missing'). Never borrow another frame.
    v2 fix 11-16: v1 picked the closest frame among frames that had objects."""
    arm_rows=[r for r in rows if r[fields['member']]==arm and int(r[fields['tier']])==int(tier)]
    times=(frame_times or {}).get(arm)
    if times is None:
        raise ValueError('frame_times[%s] (all output frame times) required'%arm)
    closest=min(times,key=lambda t:(abs(minutes(t,anchor)),t))
    eligible=[r for r in arm_rows if float(r[fields['area']])>=tier
              and dt.datetime.fromisoformat(r[fields['time']])==dt.datetime.fromisoformat(closest)]
    if not eligible: return None
    return min(eligible,key=lambda r: distance_km(station[0],station[1],float(r[fields['latitude']]),float(r[fields['longitude']])))

def onset_interval(info, event, fields):
    base=event['anchor']
    if as_bool(info.get(fields['left'])):
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

def exists_in_window(frames, arm, tier, exist_win, fields, radius_km=150):
    """Existence: any object of this arm/tier with area>=tier, time in exist_win (endpoints incl.), nearest cell <=150 km."""
    lo,hi=map(dt.datetime.fromisoformat,exist_win)
    return any(r[fields['member']]==arm and int(r[fields['tier']])==int(tier)
               and float(r[fields['area']])>=tier and lo<=dt.datetime.fromisoformat(r[fields['time']])<=hi
               and float(r[fields['nearest_cell']])<=radius_km
               for r in frames)

def compare_tier(event, frames, onsets, tier, fields, frame_times=None, station=None):
    if station is None: raise ValueError('v4: station=(lat,lon) from events_selected required')
    station=(float(station[0]),float(station[1]))
    nearest={arm:nearest_frame_objects(frames,arm,tier,event['anchor'],fields,station,frame_times) for arm in ('AI','GFS','OBS')}
    obs=nearest['OBS'];a=nearest['AI'];g=nearest['GFS']
    exists={arm:exists_in_window(frames,arm,tier,event['exist_win'],fields) for arm in ('AI','GFS')}
    existence=NEG if exists['GFS'] and not exists['AI'] else POS
    position=UNKNOWN;distances=None
    arm_dist={arm:(distance_km(float(obs[fields['latitude']]),float(obs[fields['longitude']]),
               float(nearest[arm][fields['latitude']]),float(nearest[arm][fields['longitude']]))
               if obs is not None and nearest[arm] is not None else None) for arm in ('AI','GFS')}
    if obs is not None and a is not None and g is not None:
        distances={arm:distance_km(float(obs[fields['latitude']]),float(obs[fields['longitude']]),
                  float(nearest[arm][fields['latitude']]),float(nearest[arm][fields['longitude']])) for arm in ('AI','GFS')}
        position=POS if distances['AI']<=distances['GFS']+50 else NEG
    elif (a is None) != (g is None): position='缺'
    both_missing=(a is None and g is None)
    ai_iv=onset_interval(onsets['AI'],event,fields);g_iv=onset_interval(onsets['GFS'],event,fields)
    obs_info=onsets['OBS']
    if as_bool(obs_info.get(fields['left'])) or not obs_info.get(fields['first']):time=UNKNOWN
    else: time=compare_time(ai_iv,g_iv,minutes(obs_info[fields['first']],event['anchor']))
    verdict=NEG if existence==NEG or position==NEG or time==NEG else (POS if time==POS else UNKNOWN)
    if position==UNKNOWN and verdict==POS: verdict=UNKNOWN   # v4 fix (a): position not judged -> never POS
    return {'tier_km2':tier,'position':position,'position_distance_km':distances,
            'both_positions_missing':both_missing,'obs_missing_at_anchor':obs is None,'arm_distance_km':arm_dist,'existence':existence,'exists_150km':exists,'time':time,
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

def vote_combined(events, pos24_km):
    """Prereg sec.6 combined rule + freeze clarification (v2 fix 11-16).
    events: {event: '不差于'|'差于'|'不判'}; pos24_km: {event: (d_AI_24h, d_GFS_24h)} formal 64 km2 tier.
    Each '不差于' event counts toward support only if at least one arm's 24 h position <=150 km
    for THAT event. Outcomes are only the three frozen classes."""
    determined={k:v for k,v in events.items() if v!=UNKNOWN}
    n=len(determined)
    if n<3:return '不判（样本不足）'
    def ok24(k):
        return any(p is not None and p<=150 for p in (pos24_km.get(k) or ()))
    support=sum(1 for k,v in determined.items() if v==POS and ok24(k))
    worse=sum(1 for v in determined.values() if v=='差于')
    if 3*support>=2*n:return '值得继续'
    if 3*worse>=2*n:return '搁置候选'
    return '不判'


def event_gate(obs_onset64, obs_exist150_64, radar_missing, exist24_64):
    """Prereg sec.3 symmetric gate (64 km2 tier). Returns None if passed, else reason.
    obs_onset64: dict with left_censored; obs_exist150_64: bool; radar_missing: bool (v4 radar_missing(), data-missing definition B1);
    exist24_64: {'AI':bool,'GFS':bool} at 24 h (may be None when only the obs gate is checked)."""
    if radar_missing: return '观测不可分辨·雷达缺测'
    if as_bool(obs_onset64.get('left_censored')): return '观测不可分辨·首现左删失'
    if not obs_exist150_64: return '观测不可分辨·150 km 内无对象'
    if exist24_64 is not None and not exist24_64.get('AI') and not exist24_64.get('GFS'): return '两组 24 h 均无对象'
    return None


def radar_missing(coverage_rows, sites, exist_win, scan_frac=0.5, geom_min=0.8, geom_frac=0.5):
    """v4 supplementary rule B1 (data missing only). Frames = FULL 10-min grid a-3h..a+3h (endpoints incl., 37); a grid
    time with no coverage row counts as no scan for every radar and geometric coverage 0. Missing if ANY selected radar
    (sites) lacks a matched volume scan within +/-300 s (absent from the frame's 'radars' list) in > scan_frac of frames, OR coverage150_geometric < geom_min in > geom_frac of frames.
    coverage150_valid_reflectivity is NOT used. Returns (bool, details)."""
    if not sites: raise ValueError('radar site list (all WSR-88D within 230 km) must be non-empty')
    lo,hi=map(dt.datetime.fromisoformat,exist_win)
    grid=[]; t=lo
    while t<=hi: grid.append(t); t+=dt.timedelta(minutes=10)
    byt={}
    for r in coverage_rows:
        tt=dt.datetime.fromisoformat(r['time_utc'])
        if lo<=tt<=hi:
            if tt in byt: raise ValueError('duplicate coverage row %s'%tt)
            byt[tt]=r
    off=[k for k in byt if k not in grid]
    if off: raise ValueError('coverage rows off the 10-min grid: %s'%off[:3])
    n=len(grid); absent=[g for g in grid if g not in byt]; per={}
    def radars(g): return [x for x in ((byt[g].get('radars') or '') if g in byt else '').split(';') if x]
    for s in sites: per[s]=sum(1 for g in grid if s not in radars(g))/n
    geo=sum(1 for g in grid if g not in byt or float(byt[g]['coverage150_geometric'])<geom_min)/n
    bad=[s for s,f in per.items() if f>scan_frac]
    return (bool(bad) or geo>geom_frac), {'n_frames':n,'n_rows_absent':len(absent),'missing_scan_frac':per,'radars_over':bad,'geometric_lt_frac':geo}

def gate_event(event, obs_rows, obs_onset64, coverage_rows, sites, fields, exist24_64=None):
    """Programmatic §3 gate (64 km2 tier). obs_rows: OBS object rows; obs_onset64: OBS 64 km2 onset row.
    Returns dict(reason=None|str, radar_missing, radar_detail, obs_exist150_64, obs_left_censored)."""
    rm,det=radar_missing(coverage_rows,sites,event['exist_win'])
    ex=exists_in_window(obs_rows,'OBS',64,event['exist_win'],fields)
    reason=event_gate(obs_onset64,ex,rm,exist24_64)
    return {'reason':reason,'radar_missing':rm,'radar_detail':det,'obs_exist150_64':ex,
            'obs_left_censored':as_bool(obs_onset64.get('left_censored')),'exist24_64':exist24_64}
