"""R23.4c-② ruling 2efaa6db item 3: centroid-distance reading of the judged cells (parallel reading, not the frozen one).
Same frozen judge_gc37_v3 logic (46dc4e28...), but (a) 150 km existence uses object centroid distance instead of nearest cell,
(b) onsets recomputed from object tables: first frame in the onset window with an object of area>=tier whose CENTROID is <=50 km;
left-censored if that is the first window frame; none -> right-censored. Obs treated identically.
Reuses the cell map of run_judge_gc37_formal_v2.py. Mode 'exist' = only (a) (onsets from WRF onset tables, nearest-cell per prereg sec.6 text); mode 'exist+onset' = (a)+(b).
Usage: python3 -I centroid_recheck_gc37_v1.py <lab_K_gc37_main> <nearest_verdict.json> <out.json> <exist|exist+onset>"""
import csv, json, sys, hashlib, datetime as dt, importlib.util
from pathlib import Path
HERE = Path(__file__).resolve().parent; PRE = HERE.parent/'k_gc37_prereg'
sys.path.insert(0, str(PRE)); import judge_gc37_v3 as j
assert hashlib.sha256((PRE/'judge_gc37_v3.py').read_bytes()).hexdigest().startswith('46dc4e28')
D = Path(sys.argv[1]); NEAR = json.loads(Path(sys.argv[2]).read_text()); OUT = Path(sys.argv[3]); MODE = sys.argv[4]; assert MODE in ('exist','exist+onset')
src = (HERE/'run_judge_gc37_formal_v2.py').read_text()
C = eval(src[src.index('C = {')+4: src.index('\n}\n', src.index('C = {'))+2], {'D': D})
OBS = eval(src[src.index('OBS = {')+6: src.index('}', src.index('OBS = {'))+1], {'D': D})
EV = json.loads((PRE/'event_times_gc37.json').read_text())
F = {'time':'time_utc','latitude':'lat','longitude':'lon','area':'area_km2','member':'member','tier':'tier',
     'first':'first_utc','left':'left_censored','station_lat':'station_lat','station_lon':'station_lon','nearest_cell':'centroid_distance_km'}
def rows(p): return list(csv.DictReader(open(p)))
def onset(objs, times, ev, tier):
    lo, hi = map(dt.datetime.fromisoformat, EV[ev]['onset_win'])
    win = sorted(t for t in times if lo <= dt.datetime.fromisoformat(t) <= hi)
    hit = {r['time_utc'] for r in objs if int(r['tier'])==tier and float(r['area_km2'])>=tier and float(r['centroid_distance_km'])<=50}
    first = next((t for t in win if t in hit), None)
    return {'first_utc': first, 'left_censored': bool(first and win and first == win[0])}
def judge_pair(ev, mdir, ai, gfs):
    odir, ftdir = OBS[ev]
    obs = rows(odir/f'{ev}_OBS_objects.csv'); frames = list(obs); ft = {}
    o = json.loads((ftdir/f'{ev}_frame_times.json').read_text()); ft['OBS'] = o['OBS'] if isinstance(o, dict) else o
    per = {'OBS': obs}
    for arm, m in (('AI', ai), ('GFS', gfs)):
        r = rows(mdir/f'{m}_objects.csv'); frames += r; per[arm] = r
        t = json.loads((mdir/f'{m}_frame_times.json').read_text()); ft[arm] = t[arm] if arm in t else t[m]
    res = {}
    for tier in (64, 16):
        if MODE == 'exist+onset':
            ons = {arm: onset(per[arm], ft[arm], ev, tier) for arm in ('OBS','AI','GFS')}
        else:
            ons = {'OBS': next({'first_utc': r['first_utc'] or None, 'left_censored': r['left_censored'] in ('True','true')} for r in rows(odir/f'{ev}_onset.csv') if int(r['tier'])==tier)}
            for arm, m in (('AI', ai), ('GFS', gfs)):
                ons[arm] = next({'first_utc': r['first_utc'] or None, 'left_censored': r['left_censored'] in ('True','true')} for r in rows(mdir/f'{m}_onset.csv') if int(r['tier'])==tier)
        res[tier] = j.compare_tier(EV[ev], frames, ons, tier, F, ft); res[tier]['onsets_centroid'] = ons
    res['area'] = j.combine_areas(res[64], res[16]); return res
out = {'mode': MODE, 'cells': {}, 'flips': []}
for (ev, lead), pairs in C.items():
    rec = {tag: judge_pair(ev, mdir, ai, gfs) for tag, mdir, ai, gfs in pairs}
    cell = rec['formal']['area']
    if 'appendix' in rec: cell = j.compare_steps(cell, rec['appendix']['area'])
    k = f'{ev}_{lead}'; rec['cell'] = cell; out['cells'][k] = rec
    if cell != NEAR['cells'][k]['cell']: out['flips'].append({'cell': k, 'nearest': NEAR['cells'][k]['cell'], 'centroid': cell})
out['n_cells'] = len(out['cells']); out['n_flips'] = len(out['flips'])
json.dump(out, open(OUT,'w'), ensure_ascii=False, indent=1, default=str)
for k, r in out['cells'].items(): print(k, r['cell'], '| nearest:', NEAR['cells'][k]['cell'])
print('flips', out['n_flips'], out['flips'])
