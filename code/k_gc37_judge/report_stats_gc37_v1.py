"""R23.4c-② ruling 2efaa6db item 5: Wilson 95% and 10 m wind ratios, script-generated.
Wilson: p=k/n, z=1.959964; lo,hi=(p+z^2/2n ∓ z*sqrt(p(1-p)/n+z^2/4n^2))/(1+z^2/n).
n = cells of counted events whose cell verdict is 不差于 or 非不差于 (面积敏感/步长敏感/不判 count as 不判, excluded); k = 不差于 cells.
Readings: main = counted events {R1,R2} (E1 gated by 11-16 radar threshold read literally); parallel = {E1,R1,R2}.
Wind ratio = wspd10_inst_max (station 100 km, existence window, 10-min instantaneous; WRF WIND10_SUMMARY.csv) / observed peak gust (kt*0.514444). Not a 3 s gust.
Usage: python3 -I report_stats_gc37_v1.py <lab_K_gc37_main> <verdict.json> <out.json>"""
import csv, json, math, sys
from pathlib import Path
D = Path(sys.argv[1]); V = json.loads(Path(sys.argv[2]).read_text()); OUT = Path(sys.argv[3])
PRE = Path(__file__).resolve().parent.parent/'k_gc37_prereg'
ES = json.loads((PRE/'events_selected_gc37.json').read_text())
def wilson(k, n, z=1.959964):
    if n == 0: return None
    p = k/n; d = 1+z*z/n; c = p+z*z/(2*n); h = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)); return [(c-h)/d, (c+h)/d]
out = {'wilson': {}, 'wind_ratio': {}}
for name, evs in (('main_R1R2', ('R1','R2')), ('parallel_E1R1R2', ('E1','R1','R2'))):
    cells = [V['cells'][f'{e}_{l}']['cell'] for e in evs for l in ('24h','48h','72h')]
    n = sum(c in ('不差于','非不差于') for c in cells); k = sum(c == '不差于' for c in cells)
    out['wilson'][name] = {'k': k, 'n': n, 'p': k/n if n else None, 'ci95': wilson(k, n)}
KT = 0.514444
for ev in ('R1','R2'):
    obs = float(ES[ev]['obs_kt'])*KT
    for f in ('readout_R1R2_24h','readout_R1R2_48h','readout_R1R2_48h_dt12','readout_R1R2_72h'):
        for r in csv.DictReader(open(D/f/'WIND10_SUMMARY.csv')):
            if r['event'] == ev:
                out['wind_ratio'][r['member_id']] = {'model_ms': float(r['wspd10_inst_max']), 'obs_ms': obs, 'ratio': float(r['wspd10_inst_max'])/obs}
out['wind_ratio_missing'] = 'E1: readout has no station-100-km existence-window column (only station time series) -> not computed'
json.dump(out, open(OUT,'w'), ensure_ascii=False, indent=1)
print(json.dumps(out['wilson'], ensure_ascii=False)); [print(k, round(v['ratio'],3), round(v['model_ms'],1), round(v['obs_ms'],1)) for k, v in out['wind_ratio'].items()]
