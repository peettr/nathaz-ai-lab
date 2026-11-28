"""R23.4c-③ judgement runner v4 (11-23, revised after review d2a48efe). Applies judge_gc37_v4.py.
No manual selection: (1) expansion mode checks the configured events are exactly a PREFIX of the frozen candidate order
in events_gc37x.json (N1..N13 then S1..S8); (2) the obs gate of every candidate is computed by gate_event();
(3) the events that may carry model cells are exactly the first 3k obs-gate passers in order (batches of 3; the last
batch may be smaller only when the candidate list is exhausted); main analysis = all batched events (not hand-listed);
(4) formal/appendix are assigned by dt (larger dt = formal), not by labels; (5) a lead whose 12 s integration could not
complete is entered as {"incomplete": true} and becomes '不判（积分不可完成）' while the other leads still vote.
24 h absolute position clause uses formal 64 km2 per-arm distances (arm_distance_km); 24 h incomplete -> (None,None)
and the 24 h-both-empty gate item is treated as not triggered.
Config: {"mode": "expansion"|"regression", "candidates_json": path (expansion), "old_result": path (optional, for
 secondary analysis: E1,R1,R2 from a regression-mode output), "events": {ev: {"event_times":{...}, "station":[lat,lon],
 "obs_dir":..., "frame_times_dir":..., "sites_json":..., "leads": {"24h": {"pairs": [[model_dir, ai, gfs, dt_s], ...]}
 | {"incomplete": true}, ...}}}}
Usage: python3 -I run_judge_gc37_v4.py <config.json> <out.json>"""
import csv, json, sys, hashlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import judge_gc37_v4 as j
JSHA = hashlib.sha256((HERE/'judge_gc37_v4.py').read_bytes()).hexdigest()
F = {'time':'time_utc','latitude':'lat','longitude':'lon','area':'area_km2','member':'member','tier':'tier',
     'first':'first_utc','left':'left_censored','station_lat':'station_lat','station_lon':'station_lon','nearest_cell':'nearest_cell_km'}
LEADS = ('24h', '48h', '72h'); TARGET = 6; BATCH = 3
def rows(p):
    with open(p) as fh: return list(csv.DictReader(fh))
def judge_pair(ev, E, mdir, ai, gfs):
    odir, ftdir = Path(E['obs_dir']), Path(E['frame_times_dir']); mdir = Path(mdir)
    frames = rows(odir/f'{ev}_OBS_objects.csv'); ft = {}
    o = json.loads((ftdir/f'{ev}_frame_times.json').read_text()); ft['OBS'] = o['OBS'] if isinstance(o, dict) else o
    for arm, m in (('AI', ai), ('GFS', gfs)):
        frames += rows(mdir/f'{m}_objects.csv')
        t = json.loads((mdir/f'{m}_frame_times.json').read_text())
        ft[arm] = t[arm] if arm in t else t[m]
    obs_on = {int(r['tier']): r for r in rows(odir/f'{ev}_onset.csv')}
    res = {}
    for tier in (64, 16):
        ons = {'OBS': {'first_utc': obs_on[tier]['first_utc'] or None, 'left_censored': j.as_bool(obs_on[tier]['left_censored'])}}
        for m in (ai, gfs):
            for r in rows(mdir/f'{m}_onset.csv'):
                if int(r['tier']) == tier: ons[r['member']] = {'first_utc': r['first_utc'] or None, 'left_censored': j.as_bool(r['left_censored'])}
        res[tier] = j.compare_tier(E['event_times'], frames, ons, tier, F, ft, station=E['station'])
    res['area'] = j.combine_areas(res[64], res[16])
    return res
def judge_event(ev, E):
    odir = Path(E['obs_dir']); rec = {'cells': {}}
    for lead, spec in E.get('leads', {}).items():
        if spec.get('incomplete'):
            rec['cells'][lead] = {'cell': j.INCOMPLETE, 'incomplete': True}; continue
        pairs = sorted(spec['pairs'], key=lambda p: -float(p[3]))
        assert 1 <= len(pairs) <= 2 and (len(pairs) == 1 or pairs[0][3] != pairs[1][3]), (ev, lead, pairs)
        c = {'formal': judge_pair(ev, E, *pairs[0][:3]), 'formal_dt': pairs[0][3]}
        cell = c['formal']['area']
        if len(pairs) == 2:
            c['appendix'] = judge_pair(ev, E, *pairs[1][:3]); c['appendix_dt'] = pairs[1][3]
            cell = j.compare_steps(cell, c['appendix']['area'])
        c['cell'] = cell; rec['cells'][lead] = c
    obs_rows = [r for r in rows(odir/f'{ev}_OBS_objects.csv') if r['member'] == 'OBS']
    on64 = [r for r in rows(odir/f'{ev}_onset.csv') if int(r['tier']) == 64][0]
    sites = [s['site'] for s in json.loads(Path(E['sites_json']).read_text())[ev]]
    c24 = rec['cells'].get('24h')
    ex24 = c24['formal'][64]['exists_150km'] if c24 and not c24.get('incomplete') else None
    rec['obs_gate'] = j.gate_event(E['event_times'], obs_rows, on64, rows(odir/f'{ev}_coverage.csv'), sites, F, None)
    rec['gate'] = j.gate_event(E['event_times'], obs_rows, on64, rows(odir/f'{ev}_coverage.csv'), sites, F, ex24)
    rec['station_used'] = E['station']
    rec['readout_station'] = (float(obs_rows[0]['station_lat']), float(obs_rows[0]['station_lon'])) if obs_rows else None
    rec['complete'] = all(l in rec['cells'] for l in LEADS)
    rec['vote'] = j.vote_event([rec['cells'][l]['cell'] for l in LEADS]) if rec['complete'] else None
    rec['determinable'] = rec['complete'] and rec['gate']['reason'] is None and rec['vote'] != j.UNKNOWN
    d = c24['formal'][64]['arm_distance_km'] if c24 and not c24.get('incomplete') else None
    rec['pos24_64'] = (d['AI'], d['GFS']) if d else (None, None)
    return rec
cfg = json.loads(Path(sys.argv[1]).read_text()); OUT = Path(sys.argv[2])
out = {'judge_sha256': JSHA, 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
       'config_sha256': hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest(), 'mode': cfg['mode'], 'events': {}}
for ev, E in cfg['events'].items(): out['events'][ev] = judge_event(ev, E)
if cfg['mode'] == 'expansion':
    cand = json.loads(Path(cfg['candidates_json']).read_text())
    order = [e['order'] for e in cand['main']] + [e['order'] for e in cand['secondary']]
    have = list(cfg['events'])
    assert have == order[:len(have)], ('configured events must be a prefix of the frozen order', have, order[:len(have)])
    passers = [e for e in have if out['events'][e]['obs_gate']['reason'] is None]
    batched = [e for e in have if out['events'][e]['cells']]
    assert batched == passers[:len(batched)], ('model cells only for the first obs-gate passers in order', batched, passers)
    exhausted = len(have) == len(order)
    assert len(batched) % BATCH == 0 or (exhausted and len(batched) == len(passers)), ('batches of 3 unless exhausted', len(batched))
    pending = [e for e in batched if not out['events'][e]['complete']]
    det = {e: out['events'][e]['vote'] for e in batched if out['events'][e]['determinable']}
    pos = {e: out['events'][e]['pos24_64'] for e in det}
    final = not pending and (len(det) >= TARGET or (exhausted and len(batched) == len(passers)))
    out['main'] = {'batched': batched, 'pending': pending, 'determinable': list(det), 'n': len(det),
                   'status': 'final' if final else '未完成',
                   'combined': j.vote_combined(det, pos) if final else None,
                   'next_action': None if final else ('等本批判读完成' if pending else ('下一批：' + ','.join(passers[len(batched):len(batched)+BATCH]) if passers[len(batched):] else '读出下一批候选的观测闸门'))}
    if final and cfg.get('old_result'):
        old = json.loads(Path(cfg['old_result']).read_text())['events']
        d2 = dict(det); p2 = dict(pos)
        for e in ('E1', 'R1', 'R2'):
            if old[e]['determinable']: d2[e] = old[e]['vote']; p2[e] = tuple(old[e]['pos24_64'])
        out['secondary'] = {'determinable': list(d2), 'n': len(d2), 'combined': j.vote_combined(d2, p2), 'note': '只并报'}
else:
    det = {e: r['vote'] for e, r in out['events'].items() if r['determinable']}
    out['regression_combined'] = {'determinable': list(det), 'combined': j.vote_combined(det, {e: out['events'][e]['pos24_64'] for e in det})}
json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=1, default=str)
for ev, r in out['events'].items():
    g = r['gate']; print(ev, 'gate:', g['reason'] or '过', '| radar', g['radar_missing'], {k: round(v, 3) for k, v in g['radar_detail'].get('missing_scan_frac', {}).items()}, 'geo<0.8', round(g['radar_detail']['geometric_lt_frac'], 3), 'n', g['radar_detail']['n_frames'], 'absent', g['radar_detail']['n_rows_absent'], '| obs150', g['obs_exist150_64'], 'left', g['obs_left_censored'], 'ex24', g['exist24_64'])
    print('   cells', {l: c['cell'] for l, c in r['cells'].items()}, 'vote', r['vote'], 'determinable', r['determinable'], 'pos24', r['pos24_64'])
for k in ('main', 'secondary', 'regression_combined'):
    if k in out: print(k, out[k])
