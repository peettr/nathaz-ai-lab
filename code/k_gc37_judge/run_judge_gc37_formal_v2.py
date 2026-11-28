"""R23.4c-② formal judgement runner (11-20). Applies frozen judge_gc37_v3.py (sha256 46dc4e28...) to WRF-line readouts.
Counted events: E1, R1, R2. E2/E3 gated out (11-16 ruling) -> listed only.
Step rules: 04_Decisions/R23.4c_R1R2步长裁定_20261118.md; E2/E3 24 h dt20_r2 formal vs dt15 appendix (11-16 precedent).
v2 11-21: adds R1/R2 72 h (readout_R1R2_72h MANIFEST 43d53afa...). Logic otherwise identical to v1.
Usage: python3 -I run_judge_gc37_formal_v1.py <lab_K_gc37_main dir> <out.json>"""
import csv, json, sys, hashlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
PRE = HERE.parent / 'k_gc37_prereg'
sys.path.insert(0, str(PRE))
import judge_gc37_v3 as j
assert hashlib.sha256((PRE/'judge_gc37_v3.py').read_bytes()).hexdigest().startswith('46dc4e28')
D = Path(sys.argv[1]); OUT = Path(sys.argv[2])
EV = json.loads((PRE/'event_times_gc37.json').read_text())
F = {'time':'time_utc','latitude':'lat','longitude':'lon','area':'area_km2','member':'member','tier':'tier',
     'first':'first_utc','left':'left_censored','station_lat':'station_lat','station_lon':'station_lon','nearest_cell':'nearest_cell_km'}
def rows(p): return list(csv.DictReader(open(p)))
def b(v): return v in (True,'True','true',1)
OBS = {'E1':(D/'readout_24h/obs', D/'readout_24h/obs_v2'), 'E2':(D/'readout_24h/obs', D/'readout_24h/obs_v2'),
       'E3':(D/'readout_24h/obs', D/'readout_24h/obs_v2'), 'R1':(D/'readout_R1R2_obs/obs',)*2, 'R2':(D/'readout_R1R2_obs/obs',)*2}
# cell -> list of (tag, dir, ai_member, gfs_member)
C = {
 ('E1','24h'):[('formal',D/'readout_24h/models','E1_AI_24h','E1_GFS_24h')],
 ('E1','48h'):[('formal',D/'readout_48h/models','E1_AI_48h','E1_GFS_48h')],
 ('E1','72h'):[('formal',D/'readout_72h/models','E1_AI_72h','E1_GFS_72h')],
 ('R1','24h'):[('formal',D/'readout_R1R2_24h','R1_AI_24h_dt12','R1_GFS_24h_dt12')],
 ('R1','48h'):[('formal',D/'readout_R1R2_48h','R1_AI_48h','R1_GFS_48h'),('appendix',D/'readout_R1R2_48h_dt12','R1_AI_48h_dt12','R1_GFS_48h_dt12')],
 ('R2','24h'):[('formal',D/'readout_R1R2_24h','R2_AI_24h_dt15','R2_GFS_24h_dt15')],
 ('R2','48h'):[('formal',D/'readout_R1R2_48h','R2_AI_48h','R2_GFS_48h')],
 ('R1','72h'):[('formal',D/'readout_R1R2_72h','R1_AI_72h','R1_GFS_72h')],
 ('R2','72h'):[('formal',D/'readout_R1R2_72h','R2_AI_72h','R2_GFS_72h')],
 ('E2','24h'):[('formal',D/'readout_24h/models','E2_AI_24h_dt20_r2','E2_GFS_24h'),('appendix',D/'readout_24h/models','E2_AI_24h_dt15','E2_GFS_24h_dt15')],
 ('E2','48h'):[('formal',D/'readout_48h/models','E2_AI_48h_r2','E2_GFS_48h')],
 ('E2','72h'):[('formal',D/'readout_72h/models','E2_AI_72h','E2_GFS_72h')],
 ('E3','24h'):[('formal',D/'readout_24h/models','E3_AI_24h_dt20_r2','E3_GFS_24h'),('appendix',D/'readout_24h/models','E3_AI_24h_dt15','E3_GFS_24h_dt15')],
 ('E3','48h'):[('formal',D/'readout_48h/models','E3_AI_48h','E3_GFS_48h')],
 ('E3','72h'):[('formal',D/'readout_72h/models','E3_AI_72h','E3_GFS_72h')],
}
def judge_pair(ev, mdir, ai, gfs):
    odir, ftdir = OBS[ev]
    frames = rows(odir/f'{ev}_OBS_objects.csv'); ft = {}
    o = json.loads((ftdir/f'{ev}_frame_times.json').read_text()); ft['OBS'] = o['OBS'] if isinstance(o, dict) else o
    for arm, m in (('AI', ai), ('GFS', gfs)):
        frames += rows(mdir/f'{m}_objects.csv')
        t = json.loads((mdir/f'{m}_frame_times.json').read_text())
        ft[arm] = t[arm] if arm in t else t[m]   # readout_24h keys by arm, later readouts by member_id
    obs_on = {int(r['tier']): r for r in rows(odir/f'{ev}_onset.csv')}
    res = {}
    for tier in (64, 16):
        ons = {'OBS': {'first_utc': obs_on[tier]['first_utc'] or None, 'left_censored': b(obs_on[tier]['left_censored'])}}
        for m in (ai, gfs):
            for r in rows(mdir/f'{m}_onset.csv'):
                if int(r['tier']) == tier: ons[r['member']] = {'first_utc': r['first_utc'] or None, 'left_censored': b(r['left_censored'])}
        res[tier] = j.compare_tier(EV[ev], frames, ons, tier, F, ft)
    res['area'] = j.combine_areas(res[64], res[16])
    return res
out = {'judge_sha256': hashlib.sha256((PRE/'judge_gc37_v3.py').read_bytes()).hexdigest(), 'cells': {}, 'events': {}, 'combined': None}
for (ev, lead), pairs in C.items():
    rec = {}
    for tag, mdir, ai, gfs in pairs: rec[tag] = judge_pair(ev, mdir, ai, gfs)
    cell = rec['formal']['area']
    if 'appendix' in rec: cell = j.compare_steps(cell, rec['appendix']['area'])
    rec['cell'] = cell; out['cells'][f'{ev}_{lead}'] = rec
for ev in ('E1','R1','R2','E2','E3'):
    v = [out['cells'][f'{ev}_{l}']['cell'] for l in ('24h','48h','72h') if f'{ev}_{l}' in out['cells']]
    pending = [l for l in ('24h','48h','72h') if f'{ev}_{l}' not in out['cells']]
    out['events'][ev] = {'cells': v, 'pending': pending, 'vote_now': j.vote_event(v)}
pos24 = {}
for ev in ('E1','R1','R2'):
    d = out['cells'][f'{ev}_24h']['formal'][64]['position_distance_km']
    pos24[ev] = (d['AI'], d['GFS']) if d else (None, None)
out['pos24_64'] = pos24
out['combined'] = j.vote_combined({ev: out['events'][ev]['vote_now'] for ev in ('E1','R1','R2')}, pos24)
json.dump(out, open(OUT,'w'), ensure_ascii=False, indent=1, default=str)
for k, r in out['cells'].items():
    f = r['formal']; print(k, '|', r['cell'], '| 64:', f[64]['verdict'], 'pos', f[64]['position'], f[64]['position_distance_km'], 'exist', f[64]['existence'], 'time', f[64]['time'], '| 16:', f[16]['verdict'], '|', ('appendix '+r['appendix']['area']) if 'appendix' in r else '')
print(json.dumps(out['events'], ensure_ascii=False)); print('pos24', pos24); print('combined', out['combined'])
