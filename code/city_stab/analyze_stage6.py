"""Summarize stage6_noT trace and 80-point metrics on 工作站 (no solver)."""
from pathlib import Path
import csv, json, statistics
R = Path(__file__).resolve().parent
out = {}
rows = list(csv.DictReader((R / 'stage6noT_trace.csv').open()))
finite = [r for r in rows if not r['first_nonfinite_xyz_component']]
def val(r, k): return float(r[k])
rates = []
for i in range(5, len(finite)):
    a, b = finite[i-5], finite[i]
    rates.append((int(b['step']), (val(b, 'mass_fluid')/val(a, 'mass_fluid')-1)*100))
out['trace'] = {
    'rows': len(rows), 'last_step': int(rows[-1]['step']),
    'nonfinite_any': bool(rows[-1]['first_nonfinite_xyz_component']),
    'max_speed_finite': max(val(r, 'max_u_lattice') for r in finite),
    'rho_after3000': [min(val(r, 'min_rho') for r in finite if int(r['step']) >= 3000),
                      max(val(r, 'max_rho') for r in finite if int(r['step']) >= 3000)],
    'rate1000_first_over_0p05': next(((s, v) for s, v in rates if s >= 4000 and abs(v) >= .05), None),
    'rate1000_max_abs': max(rates, key=lambda x: abs(x[1])),
    'mass3000_to_last_pct': (val(finite[-1], 'mass_fluid')/next(val(r, 'mass_fluid') for r in finite if r['step'] == '3000')-1)*100,
}
d = json.loads((R / 'stage6noT_offset_samples_a_r10.json').read_text())
points = d['rows']; assert len(points) == 80
groups = {'all': set(x['id'] for x in points), 'wall': {50, 51, 52, 54}, 'open': {23, 25, 37, 17}}
metrics = {}
for label, ids in groups.items():
    q = [r for r in points if r['id'] in ids]; assert len(q) == len(ids)
    obs = [r['after'] for r in q]
    metrics[label] = {}
    for key in ('sim_ratio', 'exp_ratio'):
        sim = [r['sample']['plus_dx'][key] for r in q]
        metrics[label][key] = {'MAE': statistics.mean(abs(x-y) for x, y in zip(sim, obs)),
                               'r': statistics.correlation(sim, obs),
                               'mean_ratio': statistics.mean(sim)/statistics.mean(obs)}
out['metrics'] = metrics
out['upstream'] = {str(p['x_local_m']): p['fraction_input'] for p in d['upstream'] if p['z_m'] == 2.0 and p['x_local_m'] in (25.0, 42.0)}
out['upstream_all_z'] = {f"{p['x_local_m']}@{p['z_m']}": p['fraction_input'] for p in d['upstream'] if p['x_local_m'] in (25.0, 42.0)}
(R / 'stage6noT_summary.json').write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n')
print(json.dumps(out, indent=2, ensure_ascii=False))
