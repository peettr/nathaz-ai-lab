"""Derive <member>_onset.csv and <member>_frame_times.json for GC37x model readouts that lack them.
Logic copied verbatim from frozen GC37 readout lab_K_gc37_main/readout_R1R2_obs/package/read_models.py
lines 71 and 83-90: frame times = all output frames (here: time_utc column of <member>_frames.csv, which lists every
10-min output frame); onset per tier in (64,16): hits = sorted times of rows with tier==tier, onset_win lo<=t<=hi and
nearest_cell_km<=50; first_utc=hits[0] or ''; left_censored = hits and hits[0]==first window frame; right_censored = no hits.
Inputs are read-only; outputs go to <out_dir>. Usage: python3 -I make_onset_frametimes_gc37x.py <results_dir> <member_id> <arm> <event> <event_times_bbox.json> <out_dir>"""
import csv, json, sys
from pathlib import Path
res, member, arm, ev, cfg, out = sys.argv[1:7]
res, out = Path(res), Path(out); out.mkdir(parents=True, exist_ok=True)
E = json.load(open(cfg))['events'][ev]
times = [r['time_utc'] for r in csv.DictReader(open(res/f'{member}_frames.csv'))]
assert times == sorted(times) and len(set(times)) == len(times)
json.dump({arm: times}, open(out/f'{member}_frame_times.json', 'w'))
rows = list(csv.DictReader(open(res/f'{member}_objects.csv')))
lo, hi = E['onset_win']
window = [t for t in times if lo <= t <= hi]
assert window
onset = []
for tier in (64, 16):
    hits = sorted({q['time_utc'] for q in rows if int(q['tier']) == tier and lo <= q['time_utc'] <= hi and float(q['nearest_cell_km']) <= 50})
    onset.append({'member': arm, 'member_id': member, 'event': ev, 'tier': tier, 'first_utc': hits[0] if hits else '',
                  'left_censored': bool(hits and hits[0] == window[0]), 'right_censored': not bool(hits), 'window_start': lo, 'window_end': hi})
with open(out/f'{member}_onset.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(onset[0])); w.writeheader(); w.writerows(onset)
print(member, onset)
